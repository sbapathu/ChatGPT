## Next Enhancements
          **Feature**                                           **Technology**
  -- Streaming responses, word by word	            FastAPI StreamingResponse + Ollama streaming API
  -- Save chat history	                                        PostgreSQL
  -- Search uploaded documents                                  RAG + ChromaDB
  -- Upload PDFs and ask questions	                        PyMuPDF + embeddings
  -- Markdown and formatted code	                            react-markdown
  -- Deploy the backend	                                      Docker + AWS ECS
  -- Deploy the frontend	                                      S3 + CloudFront



  SET DATABASE_URL=postgresql+psycopg://chatgpt_user:1234567890@localhost:5432/chatgpt_clone
  SET JWT_SECRET_KEY=1fa6795cf26d6b22141e460c42a234060d8d27a741f32e7e4aebc5a94fcb2861