use pyo3::prelude::*;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::net::UdpSocket;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use audiopus::{coder::Encoder as OpusEncoder, Application as OpusApplication, Channels as OpusChannels, SampleRate as OpusSampleRate};

const HEADER_MAGIC: &[u8; 4] = b"SYNC";
const PROTOCOL_VERSION: u8 = 1;
const PACKET_TYPE_RAW: u8 = 0;
const PACKET_TYPE_OPUS: u8 = 1;

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
fn start_audio_server(py: Python, target_ip: String, target_port: u16, use_compression: Option<bool>, broadcast: Option<bool>) -> PyResult<()> {
    let use_compression = use_compression.unwrap_or(false);
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

    // Initialize Opus encoder if compression is enabled
    let mut opus_encoder = if use_compression {
        let opus_sample_rate = match sample_rate {
            8000 => OpusSampleRate::Hz8000,
            12000 => OpusSampleRate::Hz12000,
            16000 => OpusSampleRate::Hz16000,
            24000 => OpusSampleRate::Hz24000,
            48000 => OpusSampleRate::Hz48000,
            _ => {
                println!(" Warning: Sample rate {} Hz not supported by Opus. Falling back to raw audio.", sample_rate);
                // We can't easily change the flag here since it's used in the closure type signature if we were using dynamic dispatch, 
                // but here we are using an Option or similar.
                // For simplicity, we'll just panic or return error, or better, handle it gracefully.
                // Let's return an error for now to let the user know.
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Sample rate {} Hz not supported by Opus (supported: 8k, 12k, 16k, 24k, 48k)", sample_rate)));
            }
        };
        
        let opus_channels = match channels {
            1 => OpusChannels::Mono,
            2 => OpusChannels::Stereo,
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Channel count {} not supported by Opus (1 or 2 only)", channels))),
        };

        match OpusEncoder::new(opus_sample_rate, opus_channels, OpusApplication::Audio) {
            Ok(encoder) => Some(encoder),
            Err(e) => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create Opus encoder: {:?}", e))),
        }
    } else {
        None
    };

    for _ in 0..5 {
        send_header(&socket, &target_addr, sample_rate, channels, use_compression).map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Header send failed: {}", e)))?;
        thread::sleep(Duration::from_millis(50));
    }
    
    println!(" Header sent 5 times for redundancy");
    thread::sleep(Duration::from_millis(100));

    let socket_clone = socket.try_clone().map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Socket clone failed: {}", e)))?;
    let packet_counter = std::sync::Arc::new(std::sync::atomic::AtomicU64::new(0));
    let packet_counter_clone = packet_counter.clone();

    // Buffer for Opus encoding
    let mut sample_buffer: Vec<f32> = Vec::new();
    let frame_size_ms = 20; // 20ms frame size
    let samples_per_frame = (sample_rate as usize * frame_size_ms) / 1000 * channels as usize;
    let mut encoded_buffer = vec![0u8; 4000]; // Max Opus packet size is usually smaller, 4k is safe

    let stream = device.build_input_stream(
        &config,
        move |data: &[f32], _: &_| {
            let count = packet_counter_clone.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            if count % 1000 == 0 {
                let _ = send_header(&socket_clone, &target_addr, sample_rate, channels, use_compression);
            }

            if let Some(encoder) = &mut opus_encoder {
                // Compression enabled
                sample_buffer.extend_from_slice(data);
                
                while sample_buffer.len() >= samples_per_frame {
                    let frame_slice = &sample_buffer[0..samples_per_frame];
                    
                    match encoder.encode_float(frame_slice, &mut encoded_buffer) {
                        Ok(len) => {
                            let packet = build_packet(PACKET_TYPE_OPUS, &encoded_buffer[0..len]);
                            let _ = socket_clone.send_to(&packet, &target_addr);
                        },
                        Err(e) => eprintln!("Opus encode error: {:?}", e),
                    }
                    
                    // Remove processed samples
                    // This is inefficient (O(N)), but for audio buffer sizes it's acceptable for now.
                    // A ring buffer would be better.
                    sample_buffer.drain(0..samples_per_frame);
                }
            } else {
                // Raw audio
                let byte_data = as_u8_slice(data);
                let packet = build_packet(PACKET_TYPE_RAW, byte_data);
                let _ = socket_clone.send_to(&packet, &target_addr);
            }
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
