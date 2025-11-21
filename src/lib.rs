use pyo3::prelude::*;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::net::UdpSocket;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const HEADER_MAGIC: &[u8; 4] = b"SYNC";
const PROTOCOL_VERSION: u8 = 1;
const PACKET_TYPE_RAW: u8 = 0;

fn as_u8_slice(v: &[f32]) -> &[u8] {
    unsafe {
        std::slice::from_raw_parts(v.as_ptr() as *const u8, v.len() * std::mem::size_of::<f32>())
    }
}

fn send_header(socket: &UdpSocket, target_addr: &str, sample_rate: u32, channels: u16, use_compression: bool) -> Result<(), std::io::Error> {
    let mut header = Vec::new();
    header.extend_from_slice(HEADER_MAGIC);
    header.push(PROTOCOL_VERSION);
    header.extend_from_slice(&sample_rate.to_le_bytes());
    header.extend_from_slice(&channels.to_le_bytes());
    header.push(if use_compression { 1 } else { 0 });
    socket.send_to(&header, target_addr)?;
    println!(" Sent header: {}Hz, {} channels, compression: {}", sample_rate, channels, if use_compression { "Opus" } else { "Raw" });
    Ok(())
}

fn get_timestamp_us() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_micros() as u64
}

fn build_packet(packet_type: u8, data: &[u8]) -> Vec<u8> {
    let mut packet = Vec::with_capacity(1 + 8 + 2 + data.len());
    packet.push(packet_type);
    packet.extend_from_slice(&get_timestamp_us().to_le_bytes());
    packet.extend_from_slice(&(data.len() as u16).to_le_bytes());
    packet.extend_from_slice(data);
    packet
}

#[pyfunction]
fn start_audio_server(py: Python, target_ip: String, target_port: u16, _use_compression: Option<bool>, broadcast: Option<bool>) -> PyResult<()> {
    let use_compression = false;
    let broadcast = broadcast.unwrap_or(false);
    
    let socket = UdpSocket::bind("0.0.0.0:0").map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Socket bind failed: {}", e)))?;
    
    if broadcast {
        socket.set_broadcast(true).map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Broadcast enable failed: {}", e)))?;
        println!(" Broadcast mode enabled");
    }
    
    let target_addr = format!("{}:{}", target_ip, target_port);
    println!(" Streaming audio to: {}", target_addr);

    let host = cpal::default_host();
    let device = host.default_output_device().ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No output device found"))?;
    let default_config = device.default_output_config().map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Config failed: {}", e)))?;
    
    let sample_rate = default_config.sample_rate().0;
    let channels = default_config.channels();
    let config: cpal::StreamConfig = default_config.into();
    
    println!(" Device config: {} Hz, {} channels", sample_rate, channels);

    for _ in 0..5 {
        send_header(&socket, &target_addr, sample_rate, channels, use_compression).map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Header send failed: {}", e)))?;
        thread::sleep(Duration::from_millis(50));
    }
    
    println!(" Header sent 5 times for redundancy");
    thread::sleep(Duration::from_millis(100));

    let socket_clone = socket.try_clone().map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Socket clone failed: {}", e)))?;
    let packet_counter = std::sync::Arc::new(std::sync::atomic::AtomicU64::new(0));
    let packet_counter_clone = packet_counter.clone();

    let stream = device.build_input_stream(
        &config,
        move |data: &[f32], _: &_| {
            let count = packet_counter_clone.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            if count % 1000 == 0 {
                let _ = send_header(&socket_clone, &target_addr, sample_rate, channels, use_compression);
            }
            let byte_data = as_u8_slice(data);
            let packet = build_packet(PACKET_TYPE_RAW, byte_data);
            let _ = socket_clone.send_to(&packet, &target_addr);
        },
        move |err| eprintln!("Stream error: {}", err),
        None
    ).map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Build stream failed: {}", e)))?;

    stream.play().map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Play stream failed: {}", e)))?;

    println!(" Server running with timestamps & latency measurement");
    
    // Release GIL and keep stream alive
    py.allow_threads(|| {
        // Keep the stream alive by sleeping
        // The stream will continue running until dropped
        loop {
            thread::sleep(Duration::from_millis(100));
        }
    });
    
    Ok(())
}

#[pymodule]
fn syncwave_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(start_audio_server, m)?)?;
    Ok(())
}
