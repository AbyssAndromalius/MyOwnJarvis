package handlers

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"

	"github.com/assistant/orchestrator/internal/clients"
)

// VoiceHandler handles POST /voice requests
type VoiceHandler struct {
	voiceClient clients.VoiceClientInterface
	llmClient   clients.LLMClientInterface
	logger      *slog.Logger
}

// NewVoiceHandler creates a new voice handler
func NewVoiceHandler(voiceClient clients.VoiceClientInterface, llmClient clients.LLMClientInterface, logger *slog.Logger) *VoiceHandler {
	return &VoiceHandler{
		voiceClient: voiceClient,
		llmClient:   llmClient,
		logger:      logger,
	}
}

// voiceSuccessResponse represents a successful voice processing response
type voiceSuccessResponse struct {
	Status     string   `json:"status"`
	UserID     string   `json:"user_id"`
	Confidence float64  `json:"confidence"`
	Transcript string   `json:"transcript"`
	Response   string   `json:"response"`
	ModelUsed  string   `json:"model_used"`
	Fallback   bool     `json:"fallback"`
	MemoriesUsed []string `json:"memories_used,omitempty"`
}

// ServeHTTP implements http.Handler
func (h *VoiceHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Only accept POST
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed", "")
		return
	}

	// Parse multipart form
	if err := r.ParseMultipartForm(32 << 20); err != nil { // 32 MB max
		h.logger.Warn("failed to parse multipart form", "error", err)
		writeError(w, http.StatusBadRequest, "invalid multipart form", err.Error())
		return
	}

	// Get file from form
	file, _, err := r.FormFile("file")
	if err != nil {
		h.logger.Warn("no file in request", "error", err)
		writeError(w, http.StatusBadRequest, "file is required", err.Error())
		return
	}
	defer file.Close()

	// Read WAV data
	wavData, err := io.ReadAll(file)
	if err != nil {
		h.logger.Error("failed to read wav file", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to read audio file", err.Error())
		return
	}

	h.logger.Info("processing voice request", "size_bytes", len(wavData))

	// Call Voice sidecar
	voiceResp, err := h.voiceClient.ProcessVoice(r.Context(), wavData)
	if err != nil {
		h.logger.Error("Voice sidecar request failed", "error", err)
		writeError(w, http.StatusServiceUnavailable, "voice sidecar unavailable", err.Error())
		return
	}

	// Handle different voice processing statuses
	switch voiceResp.Status {
	case "no_speech":
		h.logger.Info("no speech detected")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{
			"status": "no_speech",
		})
		return

	case "rejected":
		h.logger.Info("speaker rejected", "confidence", voiceResp.Confidence)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":     "rejected",
			"confidence": voiceResp.Confidence,
		})
		return

	case "identified", "fallback":
		// Continue to LLM processing
		h.logger.Info("speaker processed", 
			"status", voiceResp.Status, 
			"user_id", voiceResp.UserID,
			"confidence", voiceResp.Confidence)

		// Call LLM sidecar with transcript
		llmReq := &clients.ChatRequest{
			UserID:              voiceResp.UserID,
			Message:             voiceResp.Transcript,
			ConversationHistory: []clients.ConversationTurn{}, // Empty history for voice requests
		}

		llmResp, err := h.llmClient.Chat(r.Context(), llmReq)
		if err != nil {
			h.logger.Error("LLM sidecar request failed", "error", err)
			writeError(w, http.StatusServiceUnavailable, "llm sidecar unavailable", err.Error())
			return
		}

		// Build success response
		response := voiceSuccessResponse{
			Status:       voiceResp.Status,
			UserID:       voiceResp.UserID,
			Confidence:   voiceResp.Confidence,
			Transcript:   voiceResp.Transcript,
			Response:     llmResp.Response,
			ModelUsed:    llmResp.ModelUsed,
			Fallback:     voiceResp.Status == "fallback",
			MemoriesUsed: llmResp.MemoriesUsed,
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(response)
		return

	default:
		h.logger.Error("unknown voice status", "status", voiceResp.Status)
		writeError(w, http.StatusInternalServerError, "unexpected voice status", voiceResp.Status)
		return
	}
}
