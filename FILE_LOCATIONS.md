# 📁 Docu-Sync: File Locations Quick Reference

## 🗂️ **Project Structure**

```
docu-sync/
├── services/
│   └── api/
│       ├── app.py              # Main Flask application
│       ├── diff.py             # Image comparison (SSIM)
│       ├── llm_client.py       # Google Gemini AI integration
│       ├── updater.py          # GitHub integration
│       ├── requirements.txt    # Python dependencies
│       ├── .env                # Your credentials (DO NOT COMMIT)
│       ├── .env.example        # Template for credentials
│       ├── Dockerfile          # Container configuration
│       └── templates/
│           └── index.html      # Web UI
├── demo/
│   ├── demo_before.png         # Before screenshot (blue button)
│   ├── demo_after.png          # After screenshot (green button)
│   └── generate_screenshots.py # Screenshot generator
├── openapi.yaml                # OpenAPI 3.0 specification
├── docker-compose.yml          # Docker Compose configuration
├── .gitignore                  # Git ignore rules
├── README.md                   # Project documentation
├── TESTING.md                  # Testing guide
└── GEMINI_SETUP.md             # Gemini API setup guide
```

---

## 🚀 **Quick Commands**

### **Check if service is running:**
```bash
curl http://localhost:8080/health
```

### **Test change detection:**
```bash
cd path/to/docu-sync
curl -X POST http://localhost:8080/detect-change \
  -F "old_image=@demo/demo_before.png" \
  -F "new_image=@demo/demo_after.png"
```

### **Run with Docker:**
```bash
cd path/to/docu-sync
docker compose up
```

---

## ✅ **What's Complete**

- [x] Flask API service (runs on port 8080)
- [x] Change detection endpoint (`/detect-change`)
- [x] AI documentation generator (`/generate-update`)
- [x] GitHub PR creation (`/create-pr`)
- [x] Full Pipeline UI (runs all 3 steps in one click)
- [x] Demo screenshots
- [x] OpenAPI specification
- [x] Docker + docker-compose support
- [x] Environment config with `.env.example`

---

## 🎯 **What's Next**

1. Add your API keys to `services/api/.env`
2. Run `python services/api/app.py` or `docker compose up`
3. Open http://localhost:8080
4. Upload before/after screenshots and run the full pipeline
