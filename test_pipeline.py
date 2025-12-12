#!/usr/bin/env python3
"""
Test script for genomeQC pipeline
Verifies basic functionality without running full analyses
"""

import sys
import tempfile
from pathlib import Path

# Add the current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from genomeQC import EnvironmentManager, GenomeQC


def test_environment_manager():
    """Test environment manager functionality"""
    print("Testing EnvironmentManager...")
    
    env_mgr = EnvironmentManager()
    print(f"  Micromamba available: {env_mgr.micromamba_available}")
    print(f"  Module system available: {env_mgr.module_available}")
    
    # Test environment detection
    existing_envs = env_mgr._get_existing_envs()
    print(f"  Existing environments: {len(existing_envs)}")
    
    # Test module detection
    available_modules = env_mgr._get_available_modules()
    print(f"  Available modules: {len(available_modules)}")
    
    print("  ✓ EnvironmentManager tests passed")


def test_pipeline_init():
    """Test pipeline initialization"""
    print("\nTesting Pipeline Initialization...")
    
    # Create a temporary test genome file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
        f.write(">test_sequence\n")
        f.write("ATCGATCGATCGATCG\n")
        test_genome = f.name
    
    try:
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = GenomeQC(
                genome_fasta=test_genome,
                output_dir=tmpdir,
                threads=2,
                busco_dbs=['eukaryota_odb10']
            )
            
            print(f"  Genome: {pipeline.genome_fasta}")
            print(f"  Output: {pipeline.output_dir}")
            print(f"  Threads: {pipeline.threads}")
            print(f"  BUSCO DBs: {pipeline.busco_dbs}")
            
            # Check directories created
            assert pipeline.telomere_dir.exists(), "Telomere dir not created"
            assert pipeline.busco_dir.exists(), "BUSCO dir not created"
            assert pipeline.quast_dir.exists(), "QUAST dir not created"
            
            print("  ✓ Pipeline initialization tests passed")
    finally:
        # Cleanup
        Path(test_genome).unlink()


def test_quartet_check():
    """Test quartet availability check"""
    print("\nTesting Tool Availability Checks...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
        f.write(">test\nATCG\n")
        test_genome = f.name
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = GenomeQC(
                genome_fasta=test_genome,
                output_dir=tmpdir,
                threads=1,
                busco_dbs=['test_db']
            )
            
            quartet_available = pipeline.check_quartet_available()
            genomesyn_available = pipeline.check_genomesyn_available()
            
            print(f"  quartet available: {quartet_available}")
            print(f"  GenomeSyn available: {genomesyn_available}")
            print("  ✓ Tool availability checks passed")
    finally:
        Path(test_genome).unlink()


def test_help():
    """Test command line help"""
    print("\nTesting Command Line Interface...")
    import subprocess
    
    result = subprocess.run(
        ['python', 'genomeQC.py', '--help'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, "Help command failed"
    assert 'genome' in result.stdout.lower(), "Help text missing genome option"
    assert 'busco' in result.stdout.lower(), "Help text missing busco option"
    
    print("  ✓ Command line interface tests passed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Running genomeQC Pipeline Tests")
    print("=" * 60)
    
    try:
        test_environment_manager()
        test_pipeline_init()
        test_quartet_check()
        test_help()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
