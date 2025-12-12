#!/usr/bin/env python3
"""
Test script for cluster mode PBS script generation
"""

import sys
import tempfile
from pathlib import Path
import subprocess

# Add the current directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_cluster_mode_help():
    """Test that cluster mode options appear in help"""
    print("Testing cluster mode help options...")
    
    result = subprocess.run(
        ['python3', 'genomeQC.py', '--help'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, "Help command failed"
    assert '--cluster' in result.stdout, "Missing --cluster option in help"
    assert '--pbs-queue' in result.stdout, "Missing --pbs-queue option in help"
    assert '--pbs-ppn' in result.stdout, "Missing --pbs-ppn option in help"
    assert '--dry-run' in result.stdout, "Missing --dry-run option in help"
    
    print("  ✓ Cluster mode help options present")


def test_pbs_script_generation():
    """Test PBS script generation in dry-run mode"""
    print("\nTesting PBS script generation...")
    
    # Create temporary test genome
    with tempfile.TemporaryDirectory() as tmpdir:
        genome_file = Path(tmpdir) / 'test_genome.fasta'
        genome_file.write_text(">chr1\nATCGATCGATCG\n>chr2\nGCTAGCTAGCTA\n")
        
        output_dir = Path(tmpdir) / 'output'
        
        # Run in cluster dry-run mode
        result = subprocess.run([
            'python3', 'genomeQC.py',
            '-g', str(genome_file),
            '-o', str(output_dir),
            '-t', '60',
            '-b', 'eukaryota_odb10',
            '--cluster',
            '--dry-run',
            '--pbs-queue', 'test_queue',
            '--pbs-ppn', '32'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Cluster mode failed: {result.stderr}"
        
        # Check PBS scripts directory exists
        pbs_dir = output_dir / 'pbs_scripts'
        assert pbs_dir.exists(), "PBS scripts directory not created"
        
        # Check expected PBS scripts were generated
        expected_scripts = [
            'TELOMERE_GAP.pbs',
            'BUSCO_eukaryota_odb10.pbs',
            'LTR_ANALYSIS.pbs',
            'QUAST.pbs'
        ]
        
        for script_name in expected_scripts:
            script_path = pbs_dir / script_name
            assert script_path.exists(), f"PBS script {script_name} not generated"
            
            # Check script content
            content = script_path.read_text()
            assert '#!/bin/bash' in content, f"Missing shebang in {script_name}"
            assert '#PBS -N' in content, f"Missing PBS job name in {script_name}"
            assert '#PBS -q test_queue' in content, f"Wrong PBS queue in {script_name}"
            assert '#PBS -l nodes=1:ppn=32' in content, f"Wrong PBS resources in {script_name}"
            assert 'source ~/.bashrc' in content, f"Missing bashrc source in {script_name}"
            assert 'mkdir -p $WD/log' in content, f"Missing log directory creation in {script_name}"
            
            print(f"  ✓ {script_name} generated correctly")
        
        print(f"  ✓ All PBS scripts generated successfully")


def test_pbs_script_content():
    """Test PBS script content matches requirements"""
    print("\nTesting PBS script content requirements...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        genome_file = Path(tmpdir) / 'test.fasta'
        genome_file.write_text(">seq1\nATCG\n")
        
        output_dir = Path(tmpdir) / 'output'
        
        # Run with custom PBS parameters
        result = subprocess.run([
            'python3', 'genomeQC.py',
            '-g', str(genome_file),
            '-o', str(output_dir),
            '-t', '60',
            '-b', 'test_db',
            '--cluster',
            '--dry-run',
            '--pbs-queue', 'high',
            '--pbs-nodes', '1',
            '--pbs-ppn', '60',
            '--pbs-walltime', '240:00:00'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        
        # Check one script in detail
        telomere_script = output_dir / 'pbs_scripts' / 'TELOMERE_GAP.pbs'
        content = telomere_script.read_text()
        
        # Required elements from problem statement
        required_elements = [
            '#!/bin/bash',
            '#PBS -N TELOMERE_GAP',
            '#PBS -q high',
            '#PBS -l nodes=1:ppn=60',
            '#PBS -j oe',
            '#PBS -l walltime=240:00:00',
            'source ~/.bashrc',
            'pwd',
            'WD=`pwd`',
            'mkdir -p $WD/log',
            'TIME=`date +%m%d_%H%M`',
            'exec > >(tee -a'
        ]
        
        for element in required_elements:
            assert element in content, f"Missing required element: {element}"
        
        print("  ✓ PBS script contains all required elements")


def test_multiple_busco_databases():
    """Test that multiple BUSCO databases generate separate jobs"""
    print("\nTesting multiple BUSCO database jobs...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        genome_file = Path(tmpdir) / 'test.fasta'
        genome_file.write_text(">seq\nATCG\n")
        
        output_dir = Path(tmpdir) / 'output'
        
        result = subprocess.run([
            'python3', 'genomeQC.py',
            '-g', str(genome_file),
            '-o', str(output_dir),
            '-t', '60',
            '-b', 'db1', 'db2', 'db3',
            '--cluster',
            '--dry-run'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        
        pbs_dir = output_dir / 'pbs_scripts'
        
        # Check that separate jobs were created for each database
        for db_name in ['db1', 'db2', 'db3']:
            script_path = pbs_dir / f'BUSCO_{db_name}.pbs'
            assert script_path.exists(), f"BUSCO job for {db_name} not created"
            print(f"  ✓ BUSCO_{db_name}.pbs created")
        
        print("  ✓ Multiple BUSCO databases generate separate jobs")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Cluster Mode Tests")
    print("=" * 60)
    
    try:
        test_cluster_mode_help()
        test_pbs_script_generation()
        test_pbs_script_content()
        test_multiple_busco_databases()
        
        print("\n" + "=" * 60)
        print("All cluster mode tests passed! ✓")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
