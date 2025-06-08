from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
import json
import os
from systemprompt import SYSTEM_PROMPT
load_dotenv()
app = Flask(__name__)
CORS(app)
client = OpenAI()
conversations = {}
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        if session_id not in conversations:
            conversations[session_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        
        conversations[session_id].append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversations[session_id],
            stream=False
        )
        assistant_message = response.choices[0].message.content
        thinking_steps = []
        final_response = ""
        lines = assistant_message.strip().split("\n")
        for line in lines:
            try:
                parsed = json.loads(line)
                step = parsed.get("step")
                content = parsed.get("content", "")
                
                if step == "think":
                    thinking_steps.append(content)
                elif step == "result":
                    final_response = content
                    conversations[session_id].append({"role": "assistant", "content": line})
                    break
            except json.JSONDecodeError:
                final_response = assistant_message
                conversations[session_id].append({"role": "assistant", "content": assistant_message})
                break
        
        return jsonify({
            'thinking_steps': thinking_steps,
            'response': final_response,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Streaming version for real-time responses"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        if session_id not in conversations:
            conversations[session_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        conversations[session_id].append({"role": "user", "content": user_message})
        
        def generate():
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=conversations[session_id],
                    stream=True
                )
                
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                
                thinking_steps = []
                final_response = ""
                
                lines = full_response.strip().split("\n")
                for line in lines:
                    try:
                        parsed = json.loads(line)
                        step = parsed.get("step")
                        content = parsed.get("content", "")
                        
                        if step == "think":
                            thinking_steps.append(content)
                        elif step == "result":
                            final_response = content
                            conversations[session_id].append({"role": "assistant", "content": line})
                            break
                    except json.JSONDecodeError:
                        final_response = full_response
                        conversations[session_id].append({"role": "assistant", "content": full_response})
                        break
                
                yield f"data: {json.dumps({'type': 'complete', 'thinking_steps': thinking_steps, 'response': final_response})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/plain')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/history/<session_id>', methods=['GET'])
def get_history(session_id):
    """Get conversation history for a session"""
    if session_id in conversations:
        # Filter out system messages for frontend
        history = [msg for msg in conversations[session_id] if msg['role'] != 'system']
        return jsonify({'history': history})
    return jsonify({'history': []})

@app.route('/api/chat/clear/<session_id>', methods=['POST'])
def clear_history(session_id):
    """Clear conversation history for a session"""
    if session_id in conversations:
        conversations[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    return jsonify({'message': 'History cleared'})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)