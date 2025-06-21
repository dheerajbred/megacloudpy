import json
import asyncio
from flask import Flask, request, jsonify
from megacloud import Megacloud

app = Flask(__name__)

@app.route('/api/extract', methods=['POST'])
def extract_sources():
    try:
        # Get the URL from the request body
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required in request body'}), 400
        
        url = data['url']
        
        # Validate URL format
        if not url.startswith('https://megacloud.blog/embed-2/v2/e-1/'):
            return jsonify({'error': 'Invalid Megacloud URL format'}), 400
        
        # Run the async extraction
        async def extract():
            megacloud = Megacloud(url)
            return await megacloud.extract()
        
        # Execute the async function
        result = asyncio.run(extract())
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/extract', methods=['GET'])
def extract_sources_get():
    try:
        # Get the URL from query parameters
        url = request.args.get('url')
        
        if not url:
            return jsonify({'error': 'URL parameter is required'}), 400
        
        # Validate URL format
        if not url.startswith('https://megacloud.blog/embed-2/v2/e-1/'):
            return jsonify({'error': 'Invalid Megacloud URL format'}), 400
        
        # Run the async extraction
        async def extract():
            megacloud = Megacloud(url)
            return await megacloud.extract()
        
        # Execute the async function
        result = asyncio.run(extract())
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'message': 'Megacloud API',
        'endpoints': {
            'POST /api/extract': 'Extract sources from Megacloud URL (send URL in JSON body)',
            'GET /api/extract?url=<url>': 'Extract sources from Megacloud URL (send URL as query parameter)',
            'GET /health': 'Health check endpoint'
        },
        'example': {
            'POST /api/extract': {
                'body': {
                    'url': 'https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0'
                }
            },
            'GET /api/extract': {
                'url': '/api/extract?url=https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0'
            }
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080) 