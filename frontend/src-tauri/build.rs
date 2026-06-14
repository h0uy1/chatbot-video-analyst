fn main() {
    let protoc = protoc_bin_vendored::protoc_bin_path().expect("failed to find protoc");
    std::env::set_var("PROTOC", protoc);

    println!("cargo:rerun-if-changed=../../backend/chat.proto");
    tonic_build::configure()
        .build_server(false)
        .compile_protos(&["../../backend/chat.proto"], &["../../backend"])
        .expect("failed to compile gRPC proto");

    tauri_build::build()
}
