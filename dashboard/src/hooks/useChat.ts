import { useState, useCallback, useRef, useEffect } from 'react';
import type { KPI, ValueChainSegment } from '../types';

// API base URL
const API_BASE = 'http://localhost:8000';

// ============================================================================
// Types
// ============================================================================

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  artifacts?: ChatArtifacts;
}

export interface ChatArtifacts {
  thesis?: string;
  kpis: KPI[];
  valueChain: ValueChainSegment[];
}

export interface UseChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sessionId: string;
  artifacts: ChatArtifacts;
  isLoading: boolean;
  sendMessage: (message: string) => Promise<void>;
  resetChat: () => void;
  finalizeChat: () => Promise<ChatArtifacts | null>;
  saveChat: () => Promise<void>;
  loadChat: () => Promise<boolean>;
}

// ============================================================================
// Artifact Parser
// ============================================================================

function parseArtifactsFromContent(content: string): ChatArtifacts {
  const artifacts: ChatArtifacts = {
    thesis: undefined,
    kpis: [],
    valueChain: [],
  };

  // Extract thesis
  const thesisMatch = content.match(/\[THESIS_START\]([\s\S]*?)\[THESIS_END\]/);
  if (thesisMatch) {
    artifacts.thesis = thesisMatch[1].trim();
  }

  // Extract KPIs
  const kpiRegex = /\[KPI_START\]([\s\S]*?)\[KPI_END\]/g;
  let kpiMatch;
  while ((kpiMatch = kpiRegex.exec(content)) !== null) {
    try {
      const kpi = JSON.parse(kpiMatch[1].trim());
      if (kpi.name) {
        artifacts.kpis.push({
          name: kpi.name,
          target: kpi.target || '',
          rationale: kpi.rationale || '',
        });
      }
    } catch {
      // Skip malformed JSON
    }
  }

  // Extract value chain segments
  const segmentRegex = /\[SEGMENT_START\]([\s\S]*?)\[SEGMENT_END\]/g;
  let segmentMatch;
  while ((segmentMatch = segmentRegex.exec(content)) !== null) {
    try {
      const segment = JSON.parse(segmentMatch[1].trim());
      if (segment.segment) {
        artifacts.valueChain.push({
          segment: segment.segment,
          description: segment.description || '',
        });
      }
    } catch {
      // Skip malformed JSON
    }
  }

  return artifacts;
}

// Clean content for display (remove markers, keep readable text)
export function cleanContentForDisplay(content: string): string {
  let cleaned = content;

  // Replace thesis markers with formatted display
  cleaned = cleaned.replace(
    /\[THESIS_START\]([\s\S]*?)\[THESIS_END\]/g,
    (_, thesis) => `\n\n**Investment Thesis:**\n${thesis.trim()}\n\n`
  );

  // Replace KPI markers with formatted display
  cleaned = cleaned.replace(
    /\[KPI_START\]([\s\S]*?)\[KPI_END\]/g,
    (_, kpiJson) => {
      try {
        const kpi = JSON.parse(kpiJson.trim());
        return `\n• **${kpi.name}**: ${kpi.target} — ${kpi.rationale}\n`;
      } catch {
        return '';
      }
    }
  );

  // Replace segment markers with formatted display
  cleaned = cleaned.replace(
    /\[SEGMENT_START\]([\s\S]*?)\[SEGMENT_END\]/g,
    (_, segmentJson) => {
      try {
        const segment = JSON.parse(segmentJson.trim());
        return `\n• **${segment.segment}**: ${segment.description}\n`;
      } catch {
        return '';
      }
    }
  );

  // Clean up extra whitespace
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  return cleaned.trim();
}

// Generate unique ID
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// ============================================================================
// Hook
// ============================================================================

export function useChat(
  projectId?: string,
  clientName?: string,
  projectName?: string
): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => 
    projectId 
      ? `project_${projectId}` 
      : `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );
  const [artifacts, setArtifacts] = useState<ChatArtifacts>({
    thesis: undefined,
    kpis: [],
    valueChain: [],
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const saveTimeoutRef = useRef<number | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  // Aggregate artifacts from all assistant messages
  const updateAggregatedArtifacts = useCallback((msgs: ChatMessage[]) => {
    const aggregated: ChatArtifacts = {
      thesis: undefined,
      kpis: [],
      valueChain: [],
    };

    const seenKpiNames = new Set<string>();
    const seenSegments = new Set<string>();

    for (const msg of msgs) {
      if (msg.role === 'assistant' && msg.artifacts) {
        // Use latest thesis
        if (msg.artifacts.thesis) {
          aggregated.thesis = msg.artifacts.thesis;
        }

        // Collect unique KPIs
        for (const kpi of msg.artifacts.kpis) {
          if (!seenKpiNames.has(kpi.name)) {
            aggregated.kpis.push(kpi);
            seenKpiNames.add(kpi.name);
          }
        }

        // Collect unique segments
        for (const segment of msg.artifacts.valueChain) {
          if (!seenSegments.has(segment.segment)) {
            aggregated.valueChain.push(segment);
            seenSegments.add(segment.segment);
          }
        }
      }
    }

    setArtifacts(aggregated);
    return aggregated;
  }, []);

  // Save chat to backend (debounced)
  const saveChat = useCallback(async () => {
    if (!projectId || messages.length === 0) return;

    try {
      const messagesToSave = messages.map(m => ({
        role: m.role,
        content: m.content,
      }));

      await fetch(`${API_BASE}/projects/${projectId}/chat/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messagesToSave,
          artifacts: {
            thesis: artifacts.thesis,
            kpis: artifacts.kpis,
            value_chain: artifacts.valueChain,
          },
        }),
      });
    } catch (err) {
      console.error('Failed to save chat:', err);
    }
  }, [projectId, messages, artifacts]);

  // Auto-save after changes (debounced)
  const scheduleSave = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = window.setTimeout(() => {
      saveChat();
    }, 2000); // Save 2 seconds after last change
  }, [saveChat]);

  // Load chat from backend
  const loadChat = useCallback(async (): Promise<boolean> => {
    if (!projectId) return false;

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/chat/load`);
      if (!response.ok) return false;

      const data = await response.json();
      
      if (data.found && data.messages?.length > 0) {
        // Convert saved messages to ChatMessage format
        const loadedMessages: ChatMessage[] = data.messages.map((m: any, idx: number) => ({
          id: `loaded_${idx}_${Date.now()}`,
          role: m.role,
          content: m.content,
          timestamp: new Date().toISOString(),
          artifacts: m.role === 'assistant' ? parseArtifactsFromContent(m.content) : undefined,
        }));

        setMessages(loadedMessages);
        
        // Load saved artifacts or recalculate
        if (data.artifacts) {
          setArtifacts({
            thesis: data.artifacts.thesis,
            kpis: data.artifacts.kpis || [],
            valueChain: data.artifacts.value_chain || [],
          });
        } else {
          updateAggregatedArtifacts(loadedMessages);
        }

        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to load chat:', err);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [projectId, updateAggregatedArtifacts]);

  // Send message and stream response
  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim() || isStreaming) return;

    setError(null);

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: message.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);

    // Create placeholder for assistant response
    const assistantMessageId = generateId();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      artifacts: { kpis: [], valueChain: [] },
    };

    setMessages(prev => [...prev, assistantMessage]);
    setIsStreaming(true);

    // Abort any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      // Use project-specific endpoint if we have a projectId
      const endpoint = projectId 
        ? `${API_BASE}/projects/${projectId}/chat/stream`
        : `${API_BASE}/projects/chat`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: message.trim(),
          client_name: clientName || '',
          project_name: projectName || '',
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'chunk') {
                fullContent += data.content;

                // Update message content in real-time
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: fullContent }
                      : msg
                  )
                );
              } else if (data.type === 'done') {
                // Parse final artifacts
                const msgArtifacts = parseArtifactsFromContent(fullContent);

                // Update message with final artifacts
                setMessages(prev => {
                  const updated = prev.map(msg =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: fullContent, artifacts: msgArtifacts }
                      : msg
                  );
                  // Update aggregated artifacts
                  updateAggregatedArtifacts(updated);
                  return updated;
                });

                // Schedule save
                scheduleSave();
              } else if (data.type === 'error') {
                setError(data.error);
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was aborted, ignore
        return;
      }
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);

      // Remove the empty assistant message on error
      setMessages(prev => prev.filter(msg => msg.id !== assistantMessageId));
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [sessionId, projectId, clientName, projectName, isStreaming, updateAggregatedArtifacts, scheduleSave]);

  // Reset chat
  const resetChat = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setMessages([]);
    setArtifacts({ thesis: undefined, kpis: [], valueChain: [] });
    setError(null);
    setIsStreaming(false);

    // Delete session on backend
    fetch(`${API_BASE}/projects/chat/${sessionId}`, {
      method: 'DELETE',
    }).catch(() => {
      // Ignore errors
    });
  }, [sessionId]);

  // Finalize chat and get aggregated artifacts
  const finalizeChat = useCallback(async (): Promise<ChatArtifacts | null> => {
    // Save before finalizing
    await saveChat();

    try {
      const response = await fetch(`${API_BASE}/projects/chat/finalize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data = await response.json();
      
      // Convert backend format to frontend format
      const framework = data.framework || {};
      return {
        thesis: framework.thesis || artifacts.thesis,
        kpis: framework.kpis || artifacts.kpis,
        valueChain: framework.value_chain || artifacts.valueChain,
      };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to finalize chat';
      setError(errorMessage);
      return null;
    }
  }, [sessionId, artifacts, saveChat]);

  return {
    messages,
    isStreaming,
    error,
    sessionId,
    artifacts,
    isLoading,
    sendMessage,
    resetChat,
    finalizeChat,
    saveChat,
    loadChat,
  };
}
