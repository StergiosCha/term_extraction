# 📤 JSON Upload Guide - Quick Start

## Your JSON Format is READY TO USE! ✅

Your file with this structure will work perfectly:

```json
[
  {
    "source_term": "acquisition",
    "target_term": "κατάκτηση",
    "context": "Language acquisition",
    "domain": "linguistics"
  },
  {
    "source_term": "coda",
    "target_term": "έξοδος συλλαβής",
    "context": "Syllable coda",
    "domain": "phonology"
  }
]
```

## How to Upload Your File

### Step 1: Start the Server
```bash
cd /Users/graogro/Dropbox/terminology-translator3
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 2: Open Browser
```
http://localhost:8000
```

### Step 3: Scroll Down to "Upload JSON Files" Section
- Click "Select JSON File" button
- Choose your JSON file
- Select upload type: **"Glossary Import"** or **"Auto-detect"**
- Click "Upload & Process JSON"

## What Happens? (DUAL STORAGE SYSTEM)

Your glossary is stored in **TWO places** for maximum power:

### 1️⃣ Database Storage (Priority System)
✅ **Stored in CustomGlossary** - persistent database  
✅ **HIGHEST PRIORITY** - checked FIRST during translations  
✅ **Exact matching** - AI is explicitly told to use these terms  

### 2️⃣ RAG Index (Semantic Search)
✅ **Added to RAG knowledge base** - vector embeddings for semantic search  
✅ **Semantic matching** - finds related terms even with different wording  
✅ **Context-aware** - understands domain and context  

### Processing Features
✅ **Auto-detects languages** - Greek (ελληνικά) vs English automatically  
✅ **Extracts domain** - phonetics, phonology, linguistics  
✅ **Stores context** - "Language acquisition", "Syllable onset"  
✅ **Avoids duplicates** - won't import the same term twice  
✅ **Shows results** - tells you how many imported, skipped, errors  

## Flexible Format Support

Your file works with these field names (automatically detected):

### Source/Target Terms:
- `source_term` ✅ (your format)
- `source`
- `term`
- `sourceterm`

### Translation:
- `target_term` ✅ (your format)
- `target`
- `translation`
- `targetterm`

### Context:
- `context` ✅ (your format)
- `description`
- `note`

### Domain/Category:
- `domain` ✅ (your format)
- `category`

## After Upload - How Your Terms Are Used

### During Translation:
1. **Step 1**: System checks CustomGlossary database for EXACT matches
   - If you uploaded "onset → έμβαση", it will prioritize this
   - AI sees: `=== CUSTOM GLOSSARY (USE THESE TRANSLATIONS) ===`
   
2. **Step 2**: RAG searches for semantically relevant context
   - Finds similar terms, related concepts, domain-specific usage
   - Combines with your glossary for comprehensive context
   
3. **Step 3**: AI generates translation using BOTH sources
   - Your terms = PRIORITY
   - RAG context = Supporting information

### You can also:
1. **View in "Custom Glossary"** section - edit, delete terms
2. **Search terms** - use the search functionality
3. **Export** - download your glossary anytime
4. **Update** - upload new terms without duplicating

## Example: What Your Upload Will Look Like

```
✅ Successfully imported 55 glossary terms to database
✅ Added to RAG index for AI-powered semantic search

✨ Your terms are now:
• Prioritized in ALL translations
• Searchable in RAG knowledge base
• Available in Custom Glossary section

Sample of imported data:
1. acquisition → κατάκτηση (en → el) | Domain: linguistics
2. coda → έξοδος συλλαβής (en → el) | Domain: phonology
3. onset → έμβαση (en → el) | Domain: phonology
4. nasal → έρρινο (en → el) | Domain: phonetics
5. liquid → υγρό (en → el) | Domain: phonetics

⚠ Skipped 0 duplicate terms
✗ 0 errors encountered
```

## Troubleshooting

### "Invalid JSON format"
- Check your JSON is valid (use jsonlint.com)
- Make sure brackets `[ ]` match
- All strings need quotes `"like this"`
- No trailing commas

### "Missing required fields"
- Each entry MUST have source_term AND target_term
- Other fields (context, domain) are optional

### File doesn't upload
- File must end with `.json`
- Max size: reasonable (a few MB)
- Check console for errors (F12 in browser)

## Need Help?

Check browser console (F12) for detailed error messages.
Check server logs for backend errors.

---

**Your 55 linguistic terms are ready to upload!** 🎉

