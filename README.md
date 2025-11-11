# TerminologyAI - Professional Translation & Analysis

A comprehensive terminology-aware translation system with RAG (Retrieval-Augmented Generation) capabilities, supporting multiple LLM providers and specialized Greek-English translation.

## Features

### 🚀 Multi-LLM Support
- **Google Gemini 2.5 Pro** - Latest multimodal AI model
- **Anthropic Claude 3.7 Sonnet** - Advanced reasoning capabilities  
- **OpenAI GPT-5 Mini** - Efficient multimodal model
- Dynamic provider switching in real-time

### 🌐 Terminology-Aware Translation
- RAG-enhanced translation using scraped terminology databases
- Specialized Greek-English translation support
- Context-aware technical term handling
- Multiple style options (formal, informal, academic, technical)

### 🤖 Intelligent Chat System
- Terminology expert chat interface
- RAG-powered responses using authoritative sources
- Conversation history management
- Multi-language support

### 📚 Document Scraping & Processing
- Automated scraping from eleto.gr terminology resources
- PDF, DOCX, HTML document processing
- Semantic search using sentence transformers
- FAISS-powered similarity search

## Quick Start

### 1. Clone and Setup
```bash
# Create project directory
mkdir terminology-translator
cd terminology-translator

# Create directory structure
mkdir -p static/css static/js templates models data logs
mkdir -p models

# Create files
touch main.py requirements.txt .env .gitignore README.md
touch models/__init__.py auth.py email_service.py
touch static/css/style.css static/js/app.js templates/index.html
```

### 2. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Environment
Create `.env` file with your API keys:
```env
# API Keys
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here  
OPENAI_API_KEY=your_openai_api_key_here

# Database
DATABASE_URL=sqlite:///./terminology.db

# Authentication
SECRET_KEY=your_secret_key_here_change_this_in_production
ADMIN_KEY=your_admin_key_here

# Email Configuration (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_email_password
EMAIL_FROM=your_email@gmail.com
EMAIL_USE_TLS=true
```

### 4. Initialize Database
```bash
# The database will be created automatically on first run
python main.py
```

### 5. Run the Application
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000` in your browser.

## Usage

### Initial Setup
1. **Check LLM Providers**: Click "Check Providers" to verify API connections
2. **Scrape Terminology**: Use admin key to scrape terminology databases
3. **Select AI Model**: Choose your preferred LLM from the dropdown

### Translation
1. Enter text in the translation box
2. Select source and target languages
3. Choose appropriate style (formal, academic, etc.)
4. Click "Translate with Terminology"

### Chat
1. Ask questions about terminology, translation, or linguistic concepts
2. Get RAG-enhanced responses using authoritative sources
3. Maintain conversation context

## API Endpoints

### Core Translation
- `POST /api/translate-with-terminology` - RAG-enhanced translation
- `POST /api/terminology-chat` - Chat with terminology expert
- `GET /api/llm-providers` - Get available LLM providers
- `POST /api/set-default-provider` - Set default LLM

### Administration  
- `POST /api/scrape-terminology` - Scrape terminology databases (admin)
- `GET /api/status` - System status check

## Project Structure

```
terminology-translator/
├── main.py                 # Main FastAPI application
├── requirements.txt        # Python dependencies
├── .env                   # Environment configuration
├── .gitignore            # Git ignore rules
├── README.md             # Project documentation
├── models/               # Database models
│   ├── __init__.py
│   ├── user.py          # User model
│   └── session.py       # Session model
├── static/              # Static web assets
│   ├── css/
│   │   └── style.css   # Additional styles
│   └── js/
│       └── app.js      # Additional JavaScript
├── templates/           # HTML templates
│   └── index.html      # Main interface
├── data/               # Data storage
├── logs/               # Application logs
├── auth.py             # Authentication services
└── email_service.py    # Email functionality
```

## Configuration

### LLM Providers
The system automatically detects available LLM providers based on API keys:
- **Gemini**: Requires `GEMINI_API_KEY`
- **Claude**: Requires `ANTHROPIC_API_KEY`  
- **OpenAI**: Requires `OPENAI_API_KEY`

### Database
- Uses SQLite by default
- Automatic table creation
- Stores scraped documents and embeddings
- FAISS index for fast similarity search

### Terminology Sources
- Scrapes from eleto.gr terminology resources
- Processes PDF, DOCX, and HTML documents
- Creates semantic embeddings for RAG retrieval
- Updates can be triggered via admin interface

## Development

### Adding New LLM Providers
1. Add provider to `LLMProvider` enum
2. Implement generation method in `MultiLLMManager`
3. Add API key configuration
4. Update provider initialization

### Extending Terminology Sources
1. Add new scraper methods to `EletoDocumentScraper`
2. Update `find_all_document_links` for new sites
3. Implement content extraction for new formats
4. Add to scraping workflow

### Custom Styling
- Modify `templates/index.html` for UI changes
- CSS variables in `:root` for theming
- Responsive design built-in
- Modern gradient design

## Troubleshooting

### Common Issues

**LLM Provider Not Available**
- Check API key configuration in `.env`
- Verify internet connection
- Check provider status page

**Scraping Fails**
- Verify admin key
- Check website accessibility
- Review scraping logs

**Translation Errors**
- Ensure text is not too long
- Check language pair support
- Verify RAG database is populated

**Database Issues**
- Delete database files and restart
- Check write permissions
- Review database logs

### Performance Optimization

**For Large Documents**
- Increase chunk size in `TerminologyRAGSystem`
- Adjust FAISS index parameters
- Use text preprocessing

**For High Traffic**
- Implement connection pooling
- Add caching layer
- Scale with multiple workers

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review logs in `logs/` directory
- Create an issue with detailed information

## Roadmap

- [ ] Additional language pairs
- [ ] Custom terminology database upload
- [ ] API rate limiting
- [ ] User authentication system
- [ ] Batch translation interface
- [ ] Export functionality
- [ ] Advanced analytics