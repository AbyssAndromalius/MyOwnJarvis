package clients

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"time"
)

// VoiceClient handles communication with the Voice sidecar
type VoiceClient struct {
	baseURL string
	timeout time.Duration
	client  *http.Client
}

// NewVoiceClient creates a new Voice sidecar client
func NewVoiceClient(baseURL string, timeout time.Duration) *VoiceClient {
	return &VoiceClient{
		baseURL: baseURL,
		timeout: timeout,
		client: &http.Client{
			Timeout: timeout,
		},
	}
}

// VoiceResponse represents a response from the Voice sidecar
type VoiceResponse struct {
	Status     string  `json:"status"`      // "identified", "fallback", "no_speech", "rejected"
	UserID     string  `json:"user_id,omitempty"`
	Confidence float64 `json:"confidence,omitempty"`
	Transcript string  `json:"transcript,omitempty"`
}

// ProcessVoice sends a WAV file to the Voice sidecar for processing
func (c *VoiceClient) ProcessVoice(ctx context.Context, wavData []byte) (*VoiceResponse, error) {
	// Create multipart form data
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	// Add WAV file to form
	part, err := writer.CreateFormFile("file", "audio.wav")
	if err != nil {
		return nil, fmt.Errorf("failed to create form file: %w", err)
	}

	if _, err := part.Write(wavData); err != nil {
		return nil, fmt.Errorf("failed to write wav data: %w", err)
	}

	// Close multipart writer
	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("failed to close multipart writer: %w", err)
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/voice/process", &buf)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", writer.FormDataContentType())

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
		return nil, fmt.Errorf("Voice sidecar returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var voiceResp VoiceResponse
	if err := json.Unmarshal(respBody, &voiceResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &voiceResp, nil
}

// Health checks the health of the Voice sidecar
func (c *VoiceClient) Health(ctx context.Context) (time.Duration, error) {
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
