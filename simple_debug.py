#!/usr/bin/env python3
"""
Simple debug script to check what's installed
"""

print("Starting debug script...")

# Test 1: Check Python basics
print("Python is working")

# Test 2: Check numpy
try:
    import numpy as np
    print(f"✅ NumPy version: {np.__version__}")
except ImportError as e:
    print(f"❌ NumPy failed: {e}")
    exit(1)

# Test 3: Check FAISS
try:
    import faiss
    print(f"✅ FAISS imported successfully")
    print(f"FAISS version: {faiss.__version__ if hasattr(faiss, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"❌ FAISS failed: {e}")
    print("Install with: pip install faiss-cpu")
    exit(1)

# Test 4: Check sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    print("✅ SentenceTransformers imported successfully")
except ImportError as e:
    print(f"❌ SentenceTransformers failed: {e}")
    print("Install with: pip install sentence-transformers")
    exit(1)

# Test 5: Basic FAISS operation
try:
    print("Testing basic FAISS operation...")
    dimension = 10
    index = faiss.IndexFlatL2(dimension)
    test_data = np.random.random((5, dimension)).astype('float32')
    index.add(test_data)
    print(f"✅ Basic FAISS works - added {index.ntotal} vectors")
except Exception as e:
    print(f"❌ Basic FAISS failed: {e}")
    import traceback
    traceback.print_exc()

print("Debug complete!")