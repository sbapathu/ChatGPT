# ChatGPT Clone — FastAPI, React, Ollama
A local ChatGPT-style application built using **React with Vite** for the frontend, **Python with FastAPI** for the backend, and **Ollama** for local AI model integration. The application includes user registration, login with JWT-based authentication, secure password hashing using Argon2, and a protected AI chat endpoint for authenticated users.

### Note:This is not a production ready system

## Requirements
- Python 3.10+
- Node.js 18+
- Ollama

## 1. ollama setup 
      1. Download ollama from https://ollama.com/download and install it
      2. Download a model llama3.2 by using the command in command prompt: 
         **ollama pull llama3.2**
      3. Test the model in command prompt using below command
          **ollama run llama3.2**
      4. Ollama normally exposes its local API at http://localhost:11434.

## 2. Backend setup
  
  ### Create Virtual Environment
    Open new cmd terminal from project directory
    cd backend
    python -m venv .venv

  ### Active Virtual Environment
    .venv\Scripts\Activate.ps1

  ### Install Python packages dependencies 
    pip install -r requirements.txt

  ### API server run
    uvicorn app.main:app --reload --port 8000

    Backend(like Swagger API) docs: http://localhost:8000/docs

## 3. Frontend setup

  In a new cmd terminal:

  cd frontend
  npm install
  npm run dev

  Open the URL printed by Vite, usually http://localhost:5173.

## 4. JWT secret generation
  In another terminal
  python -c "import secrets; print(secrets.token_hex(32))"

## Environment variables
  SET JWT_SECRET_KEY=<JWT_SECRET_KEY>
  or 
  SET JWT_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"


## Sample API Registration payload

**API** 
  ```http
  POST /api/auth/register
  Content-Type: application/json
  ```
**Payload**
  ```json
  {
    "email": "user@example.com",
    "password": "replace-with-a-strong-password"
  }
  ```
  **A successful registration returns a token response similar to:**
  
  **Response**
  ```json
  {
    "access_token": "<signed-jwt>",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "email": "user@example.com"
    }
  }
  ```

## Example protected chat request

**API**
  ```http
  POST /api/chat
  Content-Type: application/json
  Authorization: Bearer <signed-jwt>
  ```
**Payload**
  ```json
  {
    "messages": [
      {
        "role": "user",
        "content": "Explain AWS Lambda."
      }
    ]
  }
  ```
**Response**
  A Successfully content will be delivered by API

## Troubleshooting

  ### `JWT_SECRET_KEY` is not set
    Generate a secret and export it in the terminal that starts FastAPI. The secret must remain stable across backend restarts if existing tokens should continue to work.

  ### Ollama connection error
    - Confirm Ollama is installed and running.
    - Run `ollama pull llama3.2`.
    - Check that `http://localhost:11434` is reachable locally.
    - If using a different model, set `OLLAMA_MODEL` to its exact installed name.

  ### CORS error in the browser
    The sample allows `http://localhost:5173`. If Vite uses a different port, update the `allow_origins` list in `backend/main.py` to match the frontend origin exactly.

  ### `401 Unauthorized`
    Log in again to obtain a fresh token. The sample access token expires after 30 minutes.

  ### Password hashing dependency error
    Make sure the backend virtual environment is activated and install the requirements:

    ```bash
    pip install -r requirements.txt
    ```
