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

// LearningClient handles communication with the Learning sidecar
type LearningClient struct {
	baseURL string
	timeout time.Duration
	client  *http.Client
}

// NewLearningClient creates a new Learning sidecar client
func NewLearningClient(baseURL string, timeout time.Duration) *LearningClient {
	return &LearningClient{
		baseURL: baseURL,
		timeout: timeout,
		client: &http.Client{
			Timeout: timeout,
		},
	}
}

// LearningRequest represents a request to submit learning content
type LearningRequest struct {
	UserID  string `json:"user_id"`
	Content string `json:"content"`
	Source  string `json:"source"`
}

// LearningResponse represents a response from the Learning sidecar
type LearningResponse struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

// Submit sends a learning submission to the Learning sidecar
func (c *LearningClient) Submit(ctx context.Context, req *LearningRequest) (*LearningResponse, error) {
	// Marshal request body
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/learning/submit", bytes.NewReader(body))
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
		return nil, fmt.Errorf("Learning sidecar returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var learningResp LearningResponse
	if err := json.Unmarshal(respBody, &learningResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &learningResp, nil
}

// Health checks the health of the Learning sidecar
func (c *LearningClient) Health(ctx context.Context) (time.Duration, error) {
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
