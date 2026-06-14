use chat::chat_route_client::ChatRouteClient;
use chat::UserQuery;
use tonic::Request;

pub mod chat {
    tonic::include_proto!("chat");
}

#[tauri::command]
async fn stream_chat_message(message: String) -> Result<Vec<String>, String> {
    let mut client = ChatRouteClient::connect("http://127.0.0.1:50051")
        .await
        .map_err(|error| format!("Could not connect to chat_server.py on port 50051: {error}"))?;

    let requests = message
        .chars()
        .map(|character| UserQuery {
            message: character.to_string(),
        })
        .collect::<Vec<_>>();

    let request_stream = tokio_stream::iter(requests);
    let response = client
        .user_chat(Request::new(request_stream))
        .await
        .map_err(|error| format!("chat_server.py returned an error: {error}"))?;

    let mut response_stream = response.into_inner();
    let mut messages = Vec::new();

    while let Some(response) = response_stream
        .message()
        .await
        .map_err(|error| format!("Failed while reading server stream: {error}"))?
    {
        messages.push(response.message);
    }

    Ok(messages)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![stream_chat_message])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
