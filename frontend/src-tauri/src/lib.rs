use chat::chat_route_client::ChatRouteClient;
use chat::{ChatHistoryRequest, ClearChatHistoryRequest, UserQuery};
use serde::Serialize;
use tonic::Request;

pub mod chat {
    tonic::include_proto!("chat");
}

#[derive(Serialize)]
struct ChatMessage {
    message: String,
    kind: String,
    session_id: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct HistoryMessage {
    id: i64,
    session_id: String,
    role: String,
    content: String,
    file_path: String,
    response_kind: String,
    created_at: String,
}

#[tauri::command]
async fn stream_chat_message(
    message: String,
    file_path: Option<String>,
    session_id: String,
    is_human_reply: bool,
) -> Result<Vec<ChatMessage>, String> {
    let mut client = ChatRouteClient::connect("http://127.0.0.1:50051")
        .await
        .map_err(|error| format!("Could not connect to chat_server.py on port 50051: {error}"))?;

    let requests = UserQuery {
        message,
        file_path: file_path.unwrap_or_default(),
        session_id,
        is_human_reply,
    };

    let response = client
        .user_chat(Request::new(requests))
        .await
        .map_err(|error| format!("chat_server.py returned an error: {error}"))?;

    let mut response_stream = response.into_inner();
    let mut messages = Vec::new();

    while let Some(response) = response_stream
        .message()
        .await
        .map_err(|error| format!("Failed while reading server stream: {error}"))?
    {
        let kind = match response.kind {
            1 => "assistant_message",
            2 => "clarification_request",
            3 => "error",
            _ => "unspecified",
        };

        messages.push(ChatMessage {
            message: response.message,
            kind: kind.to_string(),
            session_id: response.session_id,
        });
    }

    Ok(messages)
}

#[tauri::command]
async fn load_chat_history(session_id: String) -> Result<Vec<HistoryMessage>, String> {
    let mut client = ChatRouteClient::connect("http://127.0.0.1:50051")
        .await
        .map_err(|error| format!("Could not connect to chat_server.py on port 50051: {error}"))?;

    let response = client
        .get_chat_history(Request::new(ChatHistoryRequest { session_id }))
        .await
        .map_err(|error| format!("chat_server.py returned an error: {error}"))?;

    Ok(response
        .into_inner()
        .messages
        .into_iter()
        .map(|message| HistoryMessage {
            id: message.id,
            session_id: message.session_id,
            role: message.role,
            content: message.content,
            file_path: message.file_path,
            response_kind: message.response_kind,
            created_at: message.created_at,
        })
        .collect())
}

#[tauri::command]
async fn clear_chat_history() -> Result<String, String> {
    let mut client = ChatRouteClient::connect("http://127.0.0.1:50051")
        .await
        .map_err(|error| format!("Could not connect to chat_server.py on port 50051: {error}"))?;

    let response = client
        .clear_chat_history(Request::new(ClearChatHistoryRequest {}))
        .await
        .map_err(|error| format!("chat_server.py returned an error: {error}"))?
        .into_inner();

    if response.success {
        Ok(response.message)
    } else {
        Err(response.message)
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            stream_chat_message,
            load_chat_history,
            clear_chat_history
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
