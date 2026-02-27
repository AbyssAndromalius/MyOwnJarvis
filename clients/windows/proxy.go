package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"os/exec"
	"time"
)

// OrchestratorProxy handles communication with the WSL orchestrator
type OrchestratorProxy struct {
	baseURL string
	timeout time.Duration
	client  *http.Client
}

// NewOrchestratorProxy creates a new orchestrator proxy
func NewOrchestratorProxy(baseURL string, timeoutSeconds int) *OrchestratorProxy {
	return &OrchestratorProxy{
		baseURL: baseURL,
		timeout: time.Duration(timeoutSeconds) * time.Second,
		client: &http.Client{
			Timeout: time.Duration(timeoutSeconds) * time.Second,
		},
	}
}

// VoiceRequest represents the voice endpoint request
type VoiceRequest struct {
	AudioData           []byte    `json:"-"` // WAV file data
	MimeType            string    `json:"-"` // MIME type of the audio
	ConversationHistory []Message `json:"conversation_history,omitempty"`
}

// VoiceResponse represents the voice endpoint response
type VoiceResponse struct {
	Status     string  `json:"status"`
	UserID     string  `json:"user_id,omitempty"`
	Confidence float64 `json:"confidence,omitempty"`
	Transcript string  `json:"transcript,omitempty"`
	Response   string  `json:"response,omitempty"`
	Fallback   bool    `json:"fallback,omitempty"`
	ModelUsed  string  `json:"model_used,omitempty"`
}

// ChatRequest represents the chat endpoint request
type ChatRequest struct {
	UserID              string    `json:"user_id"`
	Message             string    `json:"message"`
	ConversationHistory []Message `json:"conversation_history,omitempty"`
}

// ChatResponse represents the chat endpoint response
type ChatResponse struct {
	Response  string `json:"response"`
	ModelUsed string `json:"model_used,omitempty"`
	UserID    string `json:"user_id,omitempty"`
}

// ForwardVoice forwards a WAV file to the orchestrator's /voice endpoint
func (p *OrchestratorProxy) ForwardVoice(audioData []byte, mimeType string, history []Message) (*VoiceResponse, error) {
	// Convert WebM to WAV if necessary
	if mimeType != "" && !isWAVFormat(mimeType) {
		var err error
		audioData, err = convertToWAV(audioData)
		if err != nil {
			return nil, fmt.Errorf("failed to convert audio to WAV: %w", err)
		}
	}

	// Create multipart form data
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// Add the audio file
	part, err := writer.CreateFormFile("file", "recording.wav")
	if err != nil {
		return nil, fmt.Errorf("failed to create form file: %w", err)
	}
	if _, err := part.Write(audioData); err != nil {
		return nil, fmt.Errorf("failed to write audio data: %w", err)
	}

	// Add conversation history as JSON field
	if len(history) > 0 {
		historyJSON, err := json.Marshal(history)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal history: %w", err)
		}
		if err := writer.WriteField("conversation_history", string(historyJSON)); err != nil {
			return nil, fmt.Errorf("failed to write history field: %w", err)
		}
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("failed to close multipart writer: %w", err)
	}

	// Create request
	url := fmt.Sprintf("%s/voice", p.baseURL)
	req, err := http.NewRequest("POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	// Send request
	resp, err := p.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("orchestrator unavailable: %w", err)
	}
	defer resp.Body.Close()

	// Read response
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("orchestrator returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var voiceResp VoiceResponse
	if err := json.Unmarshal(respBody, &voiceResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &voiceResp, nil
}

// ForwardChat forwards a text message to the orchestrator's /chat endpoint
func (p *OrchestratorProxy) ForwardChat(req ChatRequest) (*ChatResponse, error) {
	// Marshal request
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	url := fmt.Sprintf("%s/chat", p.baseURL)
	httpReq, err := http.NewRequest("POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	// Send request
	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("orchestrator unavailable: %w", err)
	}
	defer resp.Body.Close()

	// Read response
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("orchestrator returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var chatResp ChatResponse
	if err := json.Unmarshal(respBody, &chatResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &chatResp, nil
}

// CheckHealth checks if the orchestrator is reachable
func (p *OrchestratorProxy) CheckHealth() error {
	url := fmt.Sprintf("%s/health", p.baseURL)
	
	// Use a shorter timeout for health checks
	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("orchestrator returned status %d", resp.StatusCode)
	}

	return nil
}

// isWAVFormat checks if the MIME type is WAV
func isWAVFormat(mimeType string) bool {
	return mimeType == "audio/wav" || mimeType == "audio/wave" || mimeType == "audio/x-wav"
}

// convertToWAV converts audio data to WAV format using ffmpeg
func convertToWAV(inputData []byte) ([]byte, error) {
	// Create temporary files for input and output
	tmpInput, err := os.CreateTemp("", "input-*.webm")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp input file: %w", err)
	}
	defer os.Remove(tmpInput.Name())
	defer tmpInput.Close()

	tmpOutput, err := os.CreateTemp("", "output-*.wav")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp output file: %w", err)
	}
	defer os.Remove(tmpOutput.Name())
	defer tmpOutput.Close()

	// Write input data
	if _, err := tmpInput.Write(inputData); err != nil {
		return nil, fmt.Errorf("failed to write input data: %w", err)
	}
	tmpInput.Close()

	// Convert using ffmpeg
	// -ar 16000: Sample rate 16kHz (required by Whisper)
	// -ac 1: Mono channel
	// -f wav: Force WAV output format
	cmd := exec.Command("ffmpeg",
		"-i", tmpInput.Name(),
		"-ar", "16000",
		"-ac", "1",
		"-f", "wav",
		"-y", // Overwrite output file
		tmpOutput.Name(),
	)

	// Capture stderr for error messages
	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("ffmpeg conversion failed: %w, stderr: %s", err, stderr.String())
	}

	// Read converted WAV data
	wavData, err := os.ReadFile(tmpOutput.Name())
	if err != nil {
		return nil, fmt.Errorf("failed to read converted WAV: %w", err)
	}

	return wavData, nil
}
