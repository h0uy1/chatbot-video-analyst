import React, { useState, useRef, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

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

function App() {
  const [messages, setMessages] = useState([
    {
      id: "init-1",
      role: "assistant",
      content: "Hello! This is a simple conversational workspace. You can send text messages or attach a video recording of your screen to review.",
      timestamp: Date.now()
    }
  ]);
  const [inputText, setInputText] = useState("");
  const [attachedVideo, setAttachedVideo] = useState(null); // { name, size }
  const [isSending, setIsSending] = useState(false);

  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll messages list
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
        size: `${sizeInMB} MB`
      });
    }
  };

  const handleRemoveAttachment = () => {
    setAttachedVideo(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Send message
  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const outgoingText = inputText.trim();
    if ((!outgoingText && !attachedVideo) || isSending) return;

    const userMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      content: outgoingText,
      timestamp: Date.now(),
      video: attachedVideo ? { name: attachedVideo.name, size: attachedVideo.size } : null
    };

    setMessages((currentMessages) => [...currentMessages, userMsg]);

    setInputText("");
    setAttachedVideo(null);
    if (fileInputRef.current) fileInputRef.current.value = "";

    if (!outgoingText) {
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: `a-${Date.now() + 1}`,
          role: "assistant",
          content: "The gRPC server accepts text messages right now.",
          timestamp: Date.now() + 10
        }
      ]);
      return;
    }

    const assistantId = `a-${Date.now() + 1}`;
    setIsSending(true);
    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: assistantId,
        role: "assistant",
        content: "Waiting for chat_server.py...",
        timestamp: Date.now() + 10,
        pending: true
      }
    ]);

    try {
      const serverMessages = await invoke("stream_chat_message", { message: outgoingText });
      const content = serverMessages.length
        ? serverMessages.join("\n")
        : "chat_server.py finished without sending a response.";

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
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="chat-window">
      {/* Top Header */}
      <header className="chat-header">
        <VideoIcon />
        <h2>Conversational UI</h2>
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
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              accept="video/*"
              onChange={handleFileChange}
            />
            <button
              type="button"
              className="input-btn"
              onClick={() => fileInputRef.current?.click()}
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
