import json
import asyncio
import sys
import os

# Add the parent directory to the path so we can import megacloud
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from megacloud import Megacloud

def handler(event, context):
    """Netlify serverless function handler"""
    
    # Parse the request
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    
    # Handle CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Content-Type': 'application/json'
    }
    
    # Handle preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    try:
        # Route handling
        if path == '/health' or path == '/.netlify/functions/api/health':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'status': 'healthy'})
            }
        
        elif path == '/' or path == '/.netlify/functions/api/':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
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
            }
        
        elif '/extract' in path:
            url = None
            
            # Handle POST request
            if http_method == 'POST':
                try:
                    body = json.loads(event.get('body', '{}'))
                    url = body.get('url')
                except json.JSONDecodeError:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({'error': 'Invalid JSON in request body'})
                    }
            
            # Handle GET request
            elif http_method == 'GET':
                query_params = event.get('queryStringParameters', {}) or {}
                url = query_params.get('url')
            
            # Validate URL
            if not url:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'URL is required'})
                }
            
            # Validate URL format
            if not url.startswith('https://megacloud.blog/embed-2/v2/e-1/'):
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Invalid Megacloud URL format'})
                }
            
            # Run the async extraction
            async def extract():
                megacloud = Megacloud(url)
                return await megacloud.extract()
            
            try:
                result = asyncio.run(extract())
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({
                        'success': True,
                        'data': result
                    })
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
        
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Endpoint not found'})
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        } 