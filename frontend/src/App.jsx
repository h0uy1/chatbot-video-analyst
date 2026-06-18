import React, { useState, useRef, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";
import { open } from "@tauri-apps/plugin-dialog";

// Minimal icons
const PaperclipIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>
);

const SendIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
);

const VideoIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" ry="2" /></svg>
);

const XIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
);

const createInitialMessage = () => ({
  id: "init-1",
  role: "assistant",
  content: "Hello! This is a video Analyst Assistant. You can send text messages or attach a video with mp4 format to transcript or analyze.",
  timestamp: Date.now()
});

const getStoredSessionId = () => {
  const existing = localStorage.getItem("chat_session_id");
  if (existing) return existing;

  const created = crypto.randomUUID
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random()}`;

  localStorage.setItem("chat_session_id", created);
  return created;
};

const fileNameFromPath = (filePath) => filePath.split(/[\\/]/).pop();

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [attachedVideo, setAttachedVideo] = useState(null); // { name, size }
  const [isSending, setIsSending] = useState(false);
  const [sessionId, setSessionId] = useState(getStoredSessionId);
  const [awaitingClarification, setAwaitingClarification] = useState(false);

  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll messages list
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    let cancelled = false;

    const loadHistory = async () => {
      try {
        const historyMessages = await invoke("load_chat_history", { sessionId });

        if (cancelled) return;

        if (!historyMessages.length) {
          setMessages([createInitialMessage()]);
          return;
        }

        setMessages(
          historyMessages.map((message) => ({
            id: `history-${message.id}`,
            role: message.role === "user" ? "user" : "assistant",
            content: message.content,
            timestamp: Date.parse(message.createdAt) || Date.now(),
            error: message.responseKind === "error",
            video: message.filePath
              ? {
                  name: fileNameFromPath(message.filePath),
                  path: message.filePath,
                  size: "saved file"
                }
              : null
          }))
        );
      } catch {
        if (!cancelled) {
          setMessages([createInitialMessage()]);
        }
      }
    };

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Handle File picker select
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith("video/")) {
        alert("Please select a valid video file.");
        return;
      }
      const sizeInMB = (file.size / (1024 * 1024)).toFixed(1);
      setAttachedVideo({
        name: file.name,
        size: `${sizeInMB} MB`,
        path: file.path // <-- Store the file path for later use
      });
    }
  };
  const handlePickFile = async () => {
    const selected = await open({
      multiple: false,
      filters: [{ name: "Video", extensions: ["mp4", "mov", "avi", "mkv"] }],
    });

    if (selected) {
      setAttachedVideo({
        name: selected.split(/[\\/]/).pop(),  // extract filename
        path: selected,                        // this is the real absolute path
      });
    }
  };
  const handleRemoveAttachment = () => {
    setAttachedVideo(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFreshSession = async () => {
    if (isSending) return;

    setIsSending(true);

    try {
      await invoke("clear_chat_history");
      localStorage.removeItem("chat_session_id");
      setSessionId(getStoredSessionId());
      setMessages([createInitialMessage()]);
      setInputText("");
      setAttachedVideo(null);
      setAwaitingClarification(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (error) {
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: `Error clearing chat history: ${String(error)}`,
          timestamp: Date.now(),
          error: true
        }
      ]);
    } finally {
      setIsSending(false);
    }
  };

  // Send message
  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const outgoingText = inputText.trim();
    if ((!outgoingText && !attachedVideo) || isSending) return;
    const messageToSend = outgoingText || "Please transcribe this video.";
    const filePath = attachedVideo?.path;
    const isHumanReply = awaitingClarification && !filePath;

    const userMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      content: messageToSend,
      timestamp: Date.now(),
      video: attachedVideo ? { name: attachedVideo.name, size: attachedVideo.size, path: attachedVideo.path } : null
    };

    setMessages((currentMessages) => [...currentMessages, userMsg]);

    setInputText("");
    setAttachedVideo(null);
    if (fileInputRef.current) fileInputRef.current.value = "";

    const assistantId = `a-${Date.now() + 1}`;
    setIsSending(true);
    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: assistantId,
        role: "assistant",
        content: "Loading...",
        timestamp: Date.now() + 10,
        pending: true
      }
    ]);

    try {
      const serverMessages = await invoke("stream_chat_message", {
        message: messageToSend,
        filePath,
        sessionId,
        isHumanReply
      });
      const hasClarificationRequest = serverMessages.some(
        (serverMessage) => serverMessage.kind === "clarification_request"
      );
      const content = serverMessages.length
        ? serverMessages.map((serverMessage) => serverMessage.message).join("\n")
        : "chat_server.py finished without sending a response.";

      setAwaitingClarification(hasClarificationRequest);
      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === assistantId
            ? { ...message, content, pending: false }
            : message
        )
      );
    } catch (error) {
      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === assistantId
            ? { ...message, content: String(error), pending: false, error: true }
            : message
        )
      );
      setAwaitingClarification(false);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="chat-window">
      {/* Top Header */}
      <header className="chat-header">
        <div className="chat-title">
          <VideoIcon />
          <h2>Conversational UI</h2>
        </div>
        <button
          type="button"
          className="fresh-session-btn"
          onClick={handleFreshSession}
          disabled={isSending}
        >
          Fresh Session
        </button>
      </header>

      {/* Message Feed list */}
      <div className="messages-container">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-wrapper ${msg.role}`}>
            <span className="message-sender">
              {msg.role === "user" ? "You" : "Assistant"}
            </span>
            <div className={`bubble ${msg.pending ? "pending" : ""} ${msg.error ? "error" : ""}`}>
              {msg.video && (
                <div className="bubble-attachment">
                  <VideoIcon />
                  <span>
                    <strong>{msg.video.name}</strong> ({msg.video.size})
                  </span>
                </div>
              )}
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input panel container */}
      <div className="input-wrapper">
        <form className="input-form" onSubmit={handleSend}>
          
          {/* Attached File Drawer */}
          {attachedVideo && (
            <div className="attachment-preview">
              <div className="attachment-info">
                <VideoIcon />
                <span>
                  <strong>{attachedVideo.name}</strong> ({attachedVideo.size})
                </span>
              </div>
              <button
                type="button"
                className="attachment-remove-btn"
                onClick={handleRemoveAttachment}
              >
                <XIcon />
              </button>
            </div>
          )}

          {/* Typing inputs row */}
          <div className="input-row">
            <button
              type="button"
              className="input-btn"
              onClick={handlePickFile}
              title="Attach Video"
            >
              <PaperclipIcon />
            </button>

            <input
              type="text"
              className="text-input"
              placeholder="Type a message or select a video..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isSending}
            />

            <button
              type="submit"
              className="send-btn"
              disabled={isSending || (!inputText.trim() && !attachedVideo)}
            >
              <SendIcon />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default App;
