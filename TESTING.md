# 🧪 Docu-Sync API Testing Guide

Your UI works, but file uploads in browsers have security restrictions. Here's how to test all features:

## ✅ **Method 1: Test with cURL (Recommended)**

### 1. Change Detection
```bash
cd path/to/docu-sync
curl -X POST http://localhost:8080/detect-change \
  -F "old_image=@demo/demo_before.png" \
  -F "new_image=@demo/demo_after.png"
```

### 2. Documentation Writer (Gemini AI)
```bash
curl -X POST http://localhost:8080/generate-update \
  -H "Content-Type: application/json" \
  -d '{"change_summary": "Button color changed from blue to green. Submit button text updated to Continue."}'
```

### 3. GitHub PR Creation
```bash
curl -X POST http://localhost:8080/create-pr \
  -H "Content-Type: application/json" \
  -d '{"new_text": "Updated button styling and text for better UX.", "branch": "docu-sync/test-update"}'
```

---

## 📱 **Method 2: Use Postman or Insomnia**

1. Download [Postman](https://www.postman.com/downloads/)
2. Import the API endpoints
3. Test with a visual interface

---

## 🎯 **What Each Feature Does:**

1. **Change Detection**: Compares two screenshots, returns SSIM score and changed regions
2. **Documentation Writer**: Uses Google Gemini AI to generate professional documentation
3. **GitHub Integration**: Creates a pull request with your documentation updates

---

## 📊 **Expected Results:**

### Change Detection:
```json
{
  "success": true,
  "ssim": 0.9993,
  "boxes": [...],
  "summary": "Detected minimal changes..."
}
```

### Documentation Writer:
```json
{
  "success": true,
  "new_text": "The submit button has been updated..."
}
```

### GitHub PR:
```json
{
  "success": true,
  "pr_url": "https://github.com/...",
  "pr_number": 123
}
```
