import { useState } from "react";
import { setApiKey, verifyApiKey } from "../api";
import "./ApiKeyPrompt.css";

interface ApiKeyPromptProps {
  onAuthenticated: () => void;
}

export function ApiKeyPrompt({ onAuthenticated }: ApiKeyPromptProps) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const isValid = await verifyApiKey(key);
      
      if (isValid) {
        setApiKey(key);
        onAuthenticated();
      } else {
        setError("Invalid API key. Please check and try again.");
      }
    } catch (err) {
      setError("Unable to verify API key. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="api-key-prompt">
      <div className="api-key-card">
        <div className="api-key-header">
          <div className="logo">
            <span className="logo-icon">🔬</span>
            <h1>Multiplium</h1>
          </div>
          <p className="subtitle">Research Intelligence Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="api-key-form">
          <div className="form-group">
            <label htmlFor="apiKey">API Key</label>
            <input
              id="apiKey"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Enter your API key"
              autoFocus
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={!key || loading} className="submit-btn">
            {loading ? "Verifying..." : "Continue"}
          </button>
        </form>

        <p className="help-text">
          Contact your administrator if you don't have an API key.
        </p>
      </div>
    </div>
  );
}
