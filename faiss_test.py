#!/usr/bin/env python3
"""
Verbose FAISS test to find the exact failure point
"""

import numpy as np
import faiss
import sys
import traceback

def test_scaling():
    """Test with increasing sizes to find where it breaks"""
    print("Testing FAISS with increasing dataset sizes...")
    
    dimension = 384  # Same as your real embeddings
    sizes = [100, 1000, 10000, 50000, 100000, 108631]  # Up to your actual size
    
    for size in sizes:
        try:
            print(f"\n--- Testing {size:,} embeddings ---")
            
            # Create test data
            print(f"Creating {size:,} random vectors...")
            embeddings = np.random.random((size, dimension)).astype('float32')
            memory_mb = embeddings.nbytes / (1024 * 1024)
            print(f"Memory usage: {memory_mb:.1f} MB")
            
            # Create index
            print("Creating FAISS index...")
            index = faiss.IndexFlatIP(dimension)
            
            # THIS IS WHERE YOUR CODE FAILS - test normalization
            print("Testing normalization...")
            sys.stdout.flush()  # Force output before potential crash
            
            faiss.normalize_L2(embeddings)
            print("✅ Normalization successful")
            
            # Add to index
            print("Adding to index...")
            index.add(embeddings)
            print(f"✅ Index created with {index.ntotal:,} vectors")
            
            # Clean up
            del embeddings, index
            
        except KeyboardInterrupt:
            print("Interrupted by user")
            break
        except Exception as e:
            print(f"❌ FAILED at size {size:,}")
            print(f"Error: {e}")
            traceback.print_exc()
            
            # This is the breaking point
            if size > 1000:
                print(f"\nBreaking point found: between {sizes[sizes.index(size)-1]:,} and {size:,}")
                recommended = sizes[sizes.index(size)-1] // 2
                print(f"Recommended batch size: {recommended:,}")
            
            break
    
    print("\nScaling test complete")

def test_batch_normalization():
    """Test batch normalization like your fixed code"""
    print("\n--- Testing Batch Normalization Approach ---")
    
    size = 108631  # Your exact size
    dimension = 384
    batch_size = 1000
    
    try:
        print(f"Creating {size:,} embeddings...")
        embeddings = np.random.random((size, dimension)).astype('float32')
        
        print("Creating FAISS index...")
        index = faiss.IndexFlatIP(dimension)
        
        print("Normalizing in batches...")
        for i in range(0, size, batch_size):
            end_idx = min(i + batch_size, size)
            batch = embeddings[i:end_idx]
            
            print(f"Normalizing batch {i//batch_size + 1}: {i:,} to {end_idx:,}")
            sys.stdout.flush()
            
            faiss.normalize_L2(batch)
            
            if i % (batch_size * 10) == 0:
                print(f"Progress: {end_idx:,}/{size:,}")
        
        print("✅ Batch normalization successful!")
        
        print("Adding to index in batches...")
        for i in range(0, size, batch_size):
            end_idx = min(i + batch_size, size)
            batch = embeddings[i:end_idx]
            index.add(batch)
            
            if i % (batch_size * 10) == 0:
                print(f"Added: {end_idx:,}/{size:,}")
        
        print(f"✅ Success! Index contains {index.ntotal:,} vectors")
        return True
        
    except Exception as e:
        print(f"❌ Batch approach failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Verbose FAISS Test")
    print("=" * 50)
    
    try:
        # First find the breaking point
        test_scaling()
        
        # Then test the batch approach
        if test_batch_normalization():
            print("\n🎉 Batch approach works! Use this in your main code.")
        else:
            print("\n❌ Even batch approach fails. Need different solution.")
            
    except Exception as e:
        print(f"Test script failed: {e}")
        traceback.print_exc()
    
    print("\nTest complete!")