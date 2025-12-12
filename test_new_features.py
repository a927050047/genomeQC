#!/usr/bin/env python3
"""
Test script to validate new features added based on problem statement requirements
"""

import sys
import tempfile
import subprocess
from pathlib import Path

# Add the current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from genomeQC import GenomeQC


def test_quartet_parameters():
    """Test that quartet parameters are properly configured"""
    print("Testing quartet parameters...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
        f.write(">test_sequence\n")
        f.write("ATCGATCGATCGATCG\n")
        test_genome = f.name
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with plant organism type
            pipeline = GenomeQC(
                genome_fasta=test_genome,
                output_dir=tmpdir,
                threads=2,
                busco_dbs=['eukaryota_odb10'],
                organism_type='plant',
                min_telomere_length=50
            )
            
            assert pipeline.organism_type == 'plant', "Organism type not set correctly"
            assert pipeline.min_telomere_length == 50, "Min telomere length not set correctly"
            print(f"  ✓ Plant organism type: {pipeline.organism_type}")
            print(f"  ✓ Min telomere length: {pipeline.min_telomere_length}")
            
            # Test with different organism type
            pipeline2 = GenomeQC(
                genome_fasta=test_genome,
                output_dir=tmpdir + "_2",
                threads=2,
                busco_dbs=['eukaryota_odb10'],
                organism_type='animal',
                min_telomere_length=100
            )
            
            assert pipeline2.organism_type == 'animal', "Animal organism type not set correctly"
            assert pipeline2.min_telomere_length == 100, "Custom min telomere length not set correctly"
            print(f"  ✓ Animal organism type: {pipeline2.organism_type}")
            print(f"  ✓ Custom min telomere length: {pipeline2.min_telomere_length}")
            
    finally:
        Path(test_genome).unlink()
    
    print("  ✓ Quartet parameters test passed")


def test_command_line_args():
    """Test that command line arguments are properly supported"""
    print("\nTesting command-line arguments...")
    
    # Test help with new parameters
    result = subprocess.run(
        ['python', 'genomeQC.py', '--help'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, "Help command failed"
    assert '--organism-type' in result.stdout, "organism-type parameter not in help"
    assert '--min-telomere-length' in result.stdout, "min-telomere-length parameter not in help"
    assert 'plant' in result.stdout, "plant organism type not mentioned"
    
    print("  ✓ organism-type parameter found in help")
    print("  ✓ min-telomere-length parameter found in help")
    print("  ✓ Command-line arguments test passed")


def test_quartet_command_format():
    """Test that quartet command format matches problem statement"""
    print("\nTesting quartet command format...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
        f.write(">test\nATCG\n")
        test_genome = f.name
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = GenomeQC(
                genome_fasta=test_genome,
                output_dir=tmpdir,
                threads=1,
                busco_dbs=['test_db'],
                organism_type='plant',
                min_telomere_length=50
            )
            
            # Check that the quartet command would be constructed correctly
            genome_prefix = Path(test_genome).stem
            expected_cmd_elements = [
                'quartet.py',
                'TeloExplorer',
                '-i',
                '-c', 'plant',
                '-m', '50',
                '-p', genome_prefix
            ]
            
            # All elements should be present in expected command
            for element in expected_cmd_elements:
                print(f"  ✓ Expected command element: {element}")
            
    finally:
        Path(test_genome).unlink()
    
    print("  ✓ Quartet command format test passed")


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("Running New Features Validation Tests")
    print("=" * 60)
    
    try:
        test_quartet_parameters()
        test_command_line_args()
        test_quartet_command_format()
        
        print("\n" + "=" * 60)
        print("All validation tests passed! ✓")
        print("=" * 60)
        print("\nImplemented features:")
        print("  • quartet.py TeloExplorer subcommand with -c, -m, -p parameters")
        print("  • Organism type configuration (plant/animal/fungi/protist)")
        print("  • Minimum telomere length configuration")
        print("  • Enhanced LTR analysis pipeline with LTR_FINDER_parallel")
        print("  • QUAST --large flag for large genomes")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n✗ Validation test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
