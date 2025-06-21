# Deployment Guide for Netlify

This guide will help you deploy the Megacloud API to Netlify as a serverless function.

## Prerequisites

1. A Netlify account (free at [netlify.com](https://netlify.com))
2. Git repository (GitHub, GitLab, or Bitbucket)
3. Python 3.8+ (for local testing)

## Step 1: Prepare Your Repository

1. Make sure all files are committed to your Git repository:
   ```bash
   git add .
   git commit -m "Add Netlify API deployment"
   git push origin main
   ```

2. Verify your repository structure:
   ```
   ├── megacloud.py
   ├── api.py
   ├── requirements.txt
   ├── netlify.toml
   ├── functions/
   │   ├── api.py
   │   └── requirements.txt
   ├── test_api.py
   └── README.md
   ```

## Step 2: Deploy to Netlify

### Option A: Deploy via Netlify Dashboard (Recommended)

1. Go to [Netlify Dashboard](https://app.netlify.com)
2. Click "New site from Git"
3. Choose your Git provider (GitHub, GitLab, etc.)
4. Select your repository
5. Configure build settings:
   - **Build command**: Leave empty
   - **Publish directory**: Leave empty
   - **Functions directory**: `functions`
6. Click "Deploy site"

### Option B: Deploy via Netlify CLI

1. Install Netlify CLI:
   ```bash
   npm install -g netlify-cli
   ```

2. Login to Netlify:
   ```bash
   netlify login
   ```

3. Initialize the site:
   ```bash
   netlify init
   ```

4. Deploy:
   ```bash
   netlify deploy --prod
   ```

## Step 3: Configure Your Site

After deployment, Netlify will provide you with a URL like:
`https://your-site-name.netlify.app`

### Environment Variables (Optional)

No environment variables are required for basic functionality.

### Custom Domain (Optional)

1. Go to your site settings in Netlify
2. Navigate to "Domain settings"
3. Add your custom domain
4. Configure DNS as instructed

## Step 4: Test Your Deployment

### Test the API Endpoints

1. **Health Check**:
   ```bash
   curl https://your-site-name.netlify.app/health
   ```

2. **API Documentation**:
   ```bash
   curl https://your-site-name.netlify.app/
   ```

3. **Extract Sources (GET)**:
   ```bash
   curl "https://your-site-name.netlify.app/api/extract?url=https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0"
   ```

4. **Extract Sources (POST)**:
   ```bash
   curl -X POST https://your-site-name.netlify.app/api/extract \
     -H "Content-Type: application/json" \
     -d '{"url": "https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0"}'
   ```

### JavaScript Example

```javascript
// GET request
fetch('https://your-site-name.netlify.app/api/extract?url=https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0')
  .then(response => response.json())
  .then(data => console.log(data));

// POST request
fetch('https://your-site-name.netlify.app/api/extract', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    url: 'https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0'
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## Step 5: Monitor and Debug

### View Function Logs

1. Go to your Netlify dashboard
2. Navigate to "Functions" tab
3. Click on the function to view logs

### Common Issues and Solutions

1. **Function Timeout (10s limit)**:
   - The extraction process might take longer than 10 seconds
   - Consider optimizing the extraction logic
   - Add timeout handling in your client code

2. **Import Errors**:
   - Ensure all dependencies are in `functions/requirements.txt`
   - Check that `megacloud.py` is accessible from the function

3. **CORS Issues**:
   - The API includes CORS headers
   - If you still have issues, check your client configuration

4. **Cold Start Delays**:
   - First request might be slow
   - Subsequent requests will be faster
   - Consider implementing a warm-up mechanism

## Step 6: Update and Redeploy

When you make changes to your code:

1. Commit and push to your repository
2. Netlify will automatically redeploy
3. Or manually trigger a deploy from the dashboard

## Performance Optimization

1. **Function Size**: Keep dependencies minimal
2. **Caching**: Consider implementing response caching
3. **Error Handling**: Implement proper error handling in your client
4. **Rate Limiting**: Be mindful of Netlify's rate limits

## Security Considerations

1. **Input Validation**: The API validates URLs
2. **CORS**: Configured for cross-origin requests
3. **Error Messages**: Avoid exposing sensitive information in error responses

## Support

If you encounter issues:

1. Check the Netlify function logs
2. Test locally first using `python api.py`
3. Verify your repository structure
4. Check the Netlify documentation

## Cost

- Netlify Functions: 125,000 invocations/month free
- Additional invocations: $25 per 1M invocations
- Bandwidth: 100GB/month free

For most use cases, the free tier should be sufficient. 