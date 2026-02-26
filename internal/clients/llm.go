package clients

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// LLMClient handles communication with the LLM sidecar
type LLMClient struct {
	baseURL string
	timeout time.Duration
	client  *http.Client
}

// NewLLMClient creates a new LLM sidecar client
func NewLLMClient(baseURL string, timeout time.Duration) *LLMClient {
	return &LLMClient{
		baseURL: baseURL,
		timeout: timeout,
		client: &http.Client{
			Timeout: timeout,
		},
	}
}

// ConversationTurn represents a single turn in conversation history
type ConversationTurn struct {
	Role    string `json:"role"`    // "user" or "assistant"
	Content string `json:"content"` // The message content
}

// ChatRequest represents a request to the LLM sidecar
type ChatRequest struct {
	UserID              string             `json:"user_id"`
	Message             string             `json:"message"`
	ConversationHistory []ConversationTurn `json:"conversation_history,omitempty"`
}

// ChatResponse represents a response from the LLM sidecar
type ChatResponse struct {
	Response     string   `json:"response"`
	ModelUsed    string   `json:"model_used"`
	MemoriesUsed []string `json:"memories_used,omitempty"`
	UserID       string   `json:"user_id"`
}

// Chat sends a chat request to the LLM sidecar
func (c *LLMClient) Chat(ctx context.Context, req *ChatRequest) (*ChatResponse, error) {
	// Marshal request body
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/chat", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// Execute request
	resp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Check for non-2xx status codes
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("LLM sidecar returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var chatResp ChatResponse
	if err := json.Unmarshal(respBody, &chatResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &chatResp, nil
}

// Health checks the health of the LLM sidecar
func (c *LLMClient) Health(ctx context.Context) (time.Duration, error) {
	start := time.Now()

	req, err := http.NewRequestWithContext(ctx, "GET", c.baseURL+"/health", nil)
	if err != nil {
		return 0, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()

	latency := time.Since(start)

	if resp.StatusCode != http.StatusOK {
		return latency, fmt.Errorf("unhealthy status: %d", resp.StatusCode)
	}

	return latency, nil
}
