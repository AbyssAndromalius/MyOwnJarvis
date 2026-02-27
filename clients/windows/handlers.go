package main

import (
	"embed"
	"encoding/json"
	"html/template"
	"io"
	"log"
	"net/http"
	"time"
)

//go:embed templates/*
var templateFS embed.FS

// Server represents the HTTP server
type Server struct {
	config         *Config
	sessionManager *SessionManager
	proxy          *OrchestratorProxy
	templates      *template.Template
}

// NewServer creates a new HTTP server
func NewServer(cfg *Config) (*Server, error) {
	// Parse templates
	tmpl, err := template.ParseFS(templateFS, "templates/*.html")
	if err != nil {
		return nil, err
	}

	return &Server{
		config:         cfg,
		sessionManager: NewSessionManager(cfg.Session.MaxHistory),
		proxy:          NewOrchestratorProxy(cfg.Orchestrator.URL, cfg.Orchestrator.TimeoutSeconds),
		templates:      tmpl,
	}, nil
}

// IndexHandler serves the main HTML interface
func (s *Server) IndexHandler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}

	// Get or create session
	sessionID := s.getSessionID(r)
	if sessionID == "" {
		sessionID = s.createSession(w)
	}

	// Prepare template data
	voicePrefJSON, _ := json.Marshal(s.config.TTS.VoicePreference)
	
	data := map[string]interface{}{
		"TTSEnabled":           s.config.TTS.Enabled,
		"VoicePreferencesJSON": template.JS(voicePrefJSON),
		"SessionID":            sessionID,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := s.templates.ExecuteTemplate(w, "index.html", data); err != nil {
		log.Printf("Error rendering template: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}

// VoiceHandler handles voice recording submissions
func (s *Server) VoiceHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		s.sendJSONError(w, "Method not allowed", http.StatusMethodNotAllowed, "")
		return
	}

	// Get session
	sessionID := s.getSessionID(r)
	if sessionID == "" {
		s.sendJSONError(w, "Session not found", http.StatusBadRequest, "")
		return
	}
	session := s.sessionManager.GetOrCreateSession(sessionID)

	// Parse multipart form
	if err := r.ParseMultipartForm(10 << 20); err != nil { // 10MB max
		s.sendJSONError(w, "Failed to parse form", http.StatusBadRequest, err.Error())
		return
	}

	// Get audio file
	file, _, err := r.FormFile("file")
	if err != nil {
		s.sendJSONError(w, "No audio file provided", http.StatusBadRequest, err.Error())
		return
	}
	defer file.Close()

	// Read audio data
	audioData, err := io.ReadAll(file)
	if err != nil {
		s.sendJSONError(w, "Failed to read audio", http.StatusInternalServerError, err.Error())
		return
	}

	// Get MIME type (optional, for format detection)
	mimeType := r.FormValue("mime_type")

	// Get conversation history
	history := s.sessionManager.GetHistory(sessionID)

	// Forward to orchestrator
	resp, err := s.proxy.ForwardVoice(audioData, mimeType, history)
	if err != nil {
		s.sendJSONError(w, "Orchestrator unavailable", http.StatusServiceUnavailable, err.Error())
		return
	}

	// Add to conversation history if successful
	if resp.Status == "identified" || resp.Status == "fallback" {
		// Add user message
		s.sessionManager.AddMessage(sessionID, Message{
			Role:    "user",
			Content: resp.Transcript,
			UserID:  resp.UserID,
		})

		// Add assistant response
		s.sessionManager.AddMessage(sessionID, Message{
			Role:      "assistant",
			Content:   resp.Response,
			UserID:    resp.UserID,
			ModelUsed: resp.ModelUsed,
		})
	}

	// Send response
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// ChatHandler handles text-based chat messages
func (s *Server) ChatHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		s.sendJSONError(w, "Method not allowed", http.StatusMethodNotAllowed, "")
		return
	}

	// Get session
	sessionID := s.getSessionID(r)
	if sessionID == "" {
		s.sendJSONError(w, "Session not found", http.StatusBadRequest, "")
		return
	}

	// Parse request
	var req ChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		s.sendJSONError(w, "Invalid request", http.StatusBadRequest, err.Error())
		return
	}

	// Get conversation history
	history := s.sessionManager.GetHistory(sessionID)
	req.ConversationHistory = history

	// Forward to orchestrator
	resp, err := s.proxy.ForwardChat(req)
	if err != nil {
		s.sendJSONError(w, "Orchestrator unavailable", http.StatusServiceUnavailable, err.Error())
		return
	}

	// Add to conversation history
	s.sessionManager.AddMessage(sessionID, Message{
		Role:    "user",
		Content: req.Message,
		UserID:  req.UserID,
	})

	s.sessionManager.AddMessage(sessionID, Message{
		Role:      "assistant",
		Content:   resp.Response,
		UserID:    resp.UserID,
		ModelUsed: resp.ModelUsed,
	})

	// Send response
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// HealthHandler checks the health of the orchestrator
func (s *Server) HealthHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		s.sendJSONError(w, "Method not allowed", http.StatusMethodNotAllowed, "")
		return
	}

	err := s.proxy.CheckHealth()
	
	response := map[string]string{
		"orchestrator": s.config.Orchestrator.URL,
	}

	if err != nil {
		response["status"] = "orchestrator_unreachable"
		response["detail"] = err.Error()
	} else {
		response["status"] = "ok"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// ClearHistoryHandler clears the conversation history for the current session
func (s *Server) ClearHistoryHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		s.sendJSONError(w, "Method not allowed", http.StatusMethodNotAllowed, "")
		return
	}

	sessionID := s.getSessionID(r)
	if sessionID != "" {
		s.sessionManager.ClearHistory(sessionID)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// Helper functions

// getSessionID retrieves the session ID from the cookie
func (s *Server) getSessionID(r *http.Request) string {
	cookie, err := r.Cookie("session_id")
	if err != nil {
		return ""
	}
	return cookie.Value
}

// createSession creates a new session and sets the cookie
func (s *Server) createSession(w http.ResponseWriter) string {
	session := s.sessionManager.GetOrCreateSession("")
	
	cookie := &http.Cookie{
		Name:     "session_id",
		Value:    session.ID,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteStrictMode,
		MaxAge:   86400 * 30, // 30 days
	}
	http.SetCookie(w, cookie)
	
	return session.ID
}

// sendJSONError sends a JSON error response
func (s *Server) sendJSONError(w http.ResponseWriter, message string, statusCode int, detail string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	
	response := map[string]string{
		"error": message,
	}
	if detail != "" {
		response["detail"] = detail
	}
	
	json.NewEncoder(w).Encode(response)
}

// StartCleanupRoutine starts a goroutine to periodically clean up old sessions
func (s *Server) StartCleanupRoutine() {
	ticker := time.NewTicker(1 * time.Hour)
	go func() {
		for range ticker.C {
			s.sessionManager.CleanupOldSessions(24 * time.Hour)
		}
	}()
}
