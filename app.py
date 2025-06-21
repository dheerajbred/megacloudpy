from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import json
from megacloud import Megacloud
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def home():
    return jsonify({
        "message": "Megacloud API",
        "usage": "Send a POST request to /extract with a 'url' parameter containing a Megacloud embed URL",
        "example": {
            "url": "https://megacloud.blog/embed-2/v2/e-1/nGvw8vuMWbml?z=1&autoPlay=1&oa=0&asi=1"
        },
        "simple_usage": "GET /extractor?url=YOUR_MEGACLOUD_URL"
    })

@app.route('/extractor')
def extractor():
    try:
        url = request.args.get('url')
        
        if not url:
            return jsonify({
                "error": "Missing 'url' parameter",
                "usage": "Use: /extractor?url=YOUR_MEGACLOUD_URL"
            }), 400
        
        # Validate URL format
        if not url.startswith('https://megacloud.blog/embed-2/'):
            return jsonify({
                "error": "Invalid URL format. Must be a Megacloud embed URL starting with https://megacloud.blog/embed-2/"
            }), 400
        
        # Run the async extraction
        async def extract_async():
            megacloud = Megacloud(url)
            return await megacloud.extract()
        
        # Run the async function
        result = asyncio.run(extract_async())
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to extract sources from the provided URL"
        }), 500

@app.route('/extract', methods=['POST'])
def extract():
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "error": "Missing 'url' parameter",
                "usage": "Send JSON with 'url' field containing Megacloud embed URL"
            }), 400
        
        url = data['url']
        
        # Validate URL format
        if not url.startswith('https://megacloud.blog/embed-2/'):
            return jsonify({
                "error": "Invalid URL format. Must be a Megacloud embed URL starting with https://megacloud.blog/embed-2/"
            }), 400
        
        # Run the async extraction
        async def extract_async():
            megacloud = Megacloud(url)
            return await megacloud.extract()
        
        # Run the async function
        result = asyncio.run(extract_async())
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to extract sources from the provided URL"
        }), 500

@app.route('/extract', methods=['GET'])
def extract_get():
    return jsonify({
        "error": "GET method not supported",
        "usage": "Use POST method with JSON body containing 'url' parameter or use /extractor?url=YOUR_URL"
    }), 405

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), debug=False) 