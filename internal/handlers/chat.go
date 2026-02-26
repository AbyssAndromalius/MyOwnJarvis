package handlers

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/assistant/orchestrator/internal/clients"
	"github.com/assistant/orchestrator/internal/config"
)

// ChatHandler handles POST /chat requests
type ChatHandler struct {
	llmClient clients.LLMClientInterface
	config    *config.Config
	logger    *slog.Logger
}

// NewChatHandler creates a new chat handler
func NewChatHandler(llmClient clients.LLMClientInterface, cfg *config.Config, logger *slog.Logger) *ChatHandler {
	return &ChatHandler{
		llmClient: llmClient,
		config:    cfg,
		logger:    logger,
	}
}

// chatRequest represents the incoming request structure
type chatRequest struct {
	UserID              string                     `json:"user_id"`
	Message             string                     `json:"message"`
	ConversationHistory []clients.ConversationTurn `json:"conversation_history"`
}

// ServeHTTP implements http.Handler
func (h *ChatHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Only accept POST
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed", "")
		return
	}

	// Parse request body
	var req chatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.logger.Warn("failed to parse chat request", "error", err)
		writeError(w, http.StatusBadRequest, "invalid request body", err.Error())
		return
	}

	// Validate user_id
	if req.UserID == "" {
		writeError(w, http.StatusBadRequest, "user_id is required", "")
		return
	}

	if !h.config.IsValidUserID(req.UserID) {
		h.logger.Warn("invalid user_id", "user_id", req.UserID)
		writeError(w, http.StatusBadRequest, "invalid user_id", "user_id must be one of: dad, mom, teen, child")
		return
	}

	// Validate message
	if req.Message == "" {
		writeError(w, http.StatusBadRequest, "message is required", "")
		return
	}

	h.logger.Info("processing chat request", "user_id", req.UserID)

	// Call LLM sidecar
	llmReq := &clients.ChatRequest{
		UserID:              req.UserID,
		Message:             req.Message,
		ConversationHistory: req.ConversationHistory,
	}

	llmResp, err := h.llmClient.Chat(r.Context(), llmReq)
	if err != nil {
		h.logger.Error("LLM sidecar request failed", "error", err)
		writeError(w, http.StatusServiceUnavailable, "llm sidecar unavailable", err.Error())
		return
	}

	// Return LLM response
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(llmResp)
}

// writeError writes a structured error response
func writeError(w http.ResponseWriter, status int, message, detail string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{
		"error":  message,
		"detail": detail,
	})
}
