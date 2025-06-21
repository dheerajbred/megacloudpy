# Megacloud API Deployment Guide

This guide will help you deploy the Megacloud API to Render.com.

## Files Created

- `app.py` - Flask API wrapper for the megacloud script
- `requirements.txt` - Python dependencies
- `test_api.py` - Local testing script
- `DEPLOYMENT.md` - This deployment guide

## Local Testing

Before deploying, test the API locally:

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask app:
```bash
python app.py
```

3. In another terminal, test the API:
```bash
python test_api.py
```

## Deploy to Render.com

### Step 1: Create a Render Account
1. Go to [render.com](https://render.com)
2. Sign up for a free account

### Step 2: Create a New Web Service
1. Click "New +" in your dashboard
2. Select "Web Service"
3. Connect your GitHub repository (or use "Deploy from existing repository")

### Step 3: Configure the Service
- **Name**: `megacloud-api` (or any name you prefer)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`
- **Plan**: Free (or choose a paid plan if needed)

### Step 4: Deploy
1. Click "Create Web Service"
2. Render will automatically build and deploy your API
3. Wait for the build to complete (usually 2-5 minutes)

### Step 5: Get Your API URL
Once deployed, Render will provide you with a URL like:
`https://your-app-name.onrender.com`

## API Usage

### Endpoints

#### GET `/`
Returns API information and usage instructions.

#### GET `/extractor?url=YOUR_MEGACLOUD_URL` (Recommended)
Extracts video sources from a Megacloud embed URL using query parameter.

**Example:**
```
https://your-app-name.onrender.com/extractor?url=https://megacloud.blog/embed-2/v2/e-1/nGvw8vuMWbml?z=1&autoPlay=1&oa=0&asi=1
```

**Response:**
```json
{
    "sources": [...],
    "tracks": [...],
    "encrypted": true,
    "intro": [15, 95],
    "outro": [1362, 1451],
    "server": 1
}
```

#### POST `/extract`
Extracts video sources from a Megacloud embed URL using JSON body.

**Request Body:**
```json
{
    "url": "https://megacloud.blog/embed-2/v2/e-1/nGvw8vuMWbml?z=1&autoPlay=1&oa=0&asi=1"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "sources": [...],
        "tracks": [...],
        "encrypted": true,
        "intro": [15, 95],
        "outro": [1362, 1451],
        "server": 1
    }
}
```

### Example Usage

#### Simple GET Request (Recommended):
```bash
curl "https://your-app-name.onrender.com/extractor?url=https://megacloud.blog/embed-2/v2/e-1/nGvw8vuMWbml?z=1&autoPlay=1&oa=0&asi=1"
```

#### POST Request:
```bash
curl -X POST https://your-app-name.onrender.com/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://megacloud.blog/embed-2/v2/e-1/nGvw8vuMWbml?z=1&autoPlay=1&oa=0&asi=1"}'
```

## Important Notes

1. **Free Tier Limitations**: 
   - Render free tier services sleep after 15 minutes of inactivity
   - First request after sleep may take 30-60 seconds to wake up
   - 750 hours per month limit

2. **Environment Variables**: 
   - No environment variables needed for this deployment
   - The app automatically uses the PORT environment variable set by Render

3. **CORS**: 
   - CORS is enabled for all origins
   - You can call this API from any frontend application

4. **Error Handling**: 
   - The API includes proper error handling
   - Invalid URLs will return 400 status
   - Extraction failures will return 500 status

## Troubleshooting

### Build Failures
- Check that all dependencies are in `requirements.txt`
- Ensure `app.py` is in the root directory
- Verify Python version compatibility

### Runtime Errors
- Check Render logs in the dashboard
- Ensure the megacloud.py script is in the same directory as app.py
- Verify all imports are working correctly

### Performance Issues
- Free tier has cold starts (30-60 seconds after inactivity)
- Consider upgrading to a paid plan for better performance
- Monitor usage in the Render dashboard 