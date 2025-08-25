# Flask Hello World API

A simple Flask API that returns "Hello World!" when accessed.

## 🚀 Features

- Simple "Hello World" endpoint
- Health check endpoint for monitoring
- Ready for deployment on Render

## 🛠️ Local Development

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the API locally**
   ```bash
   python app.py
   ```

3. **Test the API**
   - Main endpoint: `http://localhost:5000/`
   - Health check: `http://localhost:5000/health`

## 📚 API Endpoints

- `GET /` - Returns "Hello World!" message
- `GET /health` - Health check endpoint

## 🚀 Deployment on Render

This API is pre-configured for deployment on Render:

1. **Connect your GitHub repository** to Render
2. **Create a new Web Service**
3. **Select the repository** and branch
4. **Render will automatically detect** the configuration from `render.yaml`
5. **Deploy** - your API will be live!

## 📁 Project Structure

```
sl-api/
├── app.py           # Main Flask application
├── wsgi.py          # WSGI entry point for production
├── requirements.txt  # Python dependencies
├── render.yaml      # Render deployment config
└── README.md        # This file
```

## 🔧 Configuration

The API automatically uses the `PORT` environment variable set by Render, or defaults to port 5000 for local development.

---

**Ready to deploy!** Your Flask API is configured and ready to run on Render! 🚀
