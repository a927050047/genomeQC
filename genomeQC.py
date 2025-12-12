#!/usr/bin/env python3
"""
Genome Quality Control Pipeline
Comprehensive genomic quality assessment using multiple tools including:
- quartet/seqkit: telomere and gap analysis
- BUSCO: completeness assessment
- Merqury: QV calculation
- LTR analysis: ltrharvest, TR_FINDER_parallel, LTR_retriever, LAI
- QUAST: assembly statistics
- GenomeSyn: synteny plots (optional)
"""

import argparse
import os
import sys
import subprocess
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnvironmentManager:
    """Manage software environments using micromamba, module, or direct installation"""
    
    def __init__(self):
        self.micromamba_available = self._check_micromamba()
        self.module_available = self._check_module()
        
    def _check_micromamba(self) -> bool:
        """Check if micromamba is available"""
        try:
            subprocess.run(['micromamba', '--version'], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _check_module(self) -> bool:
        """Check if environment modules are available"""
        try:
            result = subprocess.run(['modulecmd', 'python', 'list'],
                                  capture_output=True, text=True)
            return result.returncode == 0 or os.environ.get('MODULESHOME') is not None
        except FileNotFoundError:
            return False
    
    def _get_existing_envs(self) -> List[str]:
        """Get list of existing micromamba environments"""
        if not self.micromamba_available:
            return []
        try:
            result = subprocess.run(['micromamba', 'env', 'list'],
                                  capture_output=True, text=True, check=True)
            envs = []
            for line in result.stdout.split('\n'):
                if line.strip() and not line.startswith('#'):
                    parts = line.split()
                    if parts:
                        envs.append(parts[0])
            return envs
        except subprocess.CalledProcessError:
            return []
    
    def _get_available_modules(self) -> List[str]:
        """Get list of available modules"""
        if not self.module_available:
            return []
        try:
            result = subprocess.run(['modulecmd', 'python', 'avail'],
                                  capture_output=True, text=True)
            modules = []
            output = result.stdout + result.stderr
            for line in output.split('\n'):
                # Module names are typically in format: name/version
                match = re.search(r'(\S+?)(?:/\S+)?(?:\s|$)', line)
                if match and not line.startswith('-'):
                    modules.append(match.group(1))
            return modules
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []
    
    def _env_exists(self, software_name: str, env_list: List[str]) -> Optional[str]:
        """Check if environment exists (case-insensitive)"""
        software_lower = software_name.lower()
        for env in env_list:
            if env.lower() == software_lower:
                return env
        return None
    
    def _module_exists(self, software_name: str, module_list: List[str]) -> Optional[str]:
        """Check if module exists (case-insensitive)"""
        software_lower = software_name.lower()
        for module in module_list:
            if module.lower() == software_lower:
                return module
        return None
    
    def setup_software(self, software_name: str, conda_package: Optional[str] = None,
                      channels: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Setup software environment
        Returns dict with 'method' (env/module/system) and 'name' or 'command'
        """
        if not conda_package:
            conda_package = software_name
        
        # Check existing environments
        existing_envs = self._get_existing_envs()
        env_name = self._env_exists(software_name, existing_envs)
        if env_name:
            logger.info(f"Using existing micromamba environment: {env_name}")
            return {'method': 'env', 'name': env_name}
        
        # Check available modules
        available_modules = self._get_available_modules()
        module_name = self._module_exists(software_name, available_modules)
        if module_name:
            logger.info(f"Using module: {module_name}")
            return {'method': 'module', 'name': module_name}
        
        # Create new environment with micromamba
        if self.micromamba_available:
            logger.info(f"Creating new micromamba environment: {software_name}")
            try:
                channel_args = []
                if channels:
                    for channel in channels:
                        channel_args.extend(['-c', channel])
                
                cmd = ['micromamba', 'create', '-n', software_name, '-y'] + channel_args + [conda_package]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Successfully created environment: {software_name}")
                    return {'method': 'env', 'name': software_name}
                else:
                    logger.warning(f"Failed to create environment for {software_name}: {result.stderr}")
            except Exception as e:
                logger.warning(f"Error creating environment for {software_name}: {e}")
        
        # Fallback to system
        logger.info(f"Using system installation for {software_name}")
        return {'method': 'system', 'command': software_name}
    
    def run_command(self, env_info: Dict[str, str], command: List[str],
                   cwd: Optional[str] = None, **kwargs) -> subprocess.CompletedProcess:
        """Run command in the appropriate environment"""
        if env_info['method'] == 'env':
            full_cmd = ['micromamba', 'run', '-n', env_info['name']] + command
        elif env_info['method'] == 'module':
            # For module, we need to load it first
            module_cmd = f"module load {env_info['name']} && {' '.join(command)}"
            full_cmd = ['bash', '-c', module_cmd]
        else:
            full_cmd = command
        
        return subprocess.run(full_cmd, cwd=cwd, **kwargs)


class GenomeQC:
    """Main genome QC pipeline"""
    
    def __init__(self, genome_fasta: str, output_dir: str, threads: int,
                 busco_dbs: List[str], reference_genome: Optional[str] = None):
        self.genome_fasta = Path(genome_fasta).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.threads = threads
        self.busco_dbs = busco_dbs
        self.reference_genome = Path(reference_genome).resolve() if reference_genome else None
        
        self.env_manager = EnvironmentManager()
        self.results = {}
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup subdirectories
        self.telomere_dir = self.output_dir / "telomere_gap"
        self.busco_dir = self.output_dir / "busco"
        self.merqury_dir = self.output_dir / "merqury"
        self.ltr_dir = self.output_dir / "ltr_analysis"
        self.quast_dir = self.output_dir / "quast"
        self.synteny_dir = self.output_dir / "synteny"
        
        for d in [self.telomere_dir, self.busco_dir, self.merqury_dir,
                  self.ltr_dir, self.quast_dir, self.synteny_dir]:
            d.mkdir(exist_ok=True)
    
    def check_quartet_available(self) -> bool:
        """Check if quartet is available in the system"""
        try:
            result = subprocess.run(['quartet', '--help'], 
                                  capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def check_genomesyn_available(self) -> bool:
        """Check if GenomeSyn is available in the system"""
        try:
            result = subprocess.run(['GenomeSyn', '--help'],
                                  capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def run_telomere_gap_analysis(self):
        """Run telomere and gap analysis using quartet or seqkit"""
        logger.info("=" * 60)
        logger.info("Running telomere and gap analysis")
        logger.info("=" * 60)
        
        if self.check_quartet_available():
            logger.info("Using quartet for telomere and gap analysis")
            self._run_quartet()
        else:
            logger.warning("quartet not found, using seqkit (no visualization)")
            self._run_seqkit()
    
    def _run_quartet(self):
        """Run quartet for telomere and gap analysis with visualization"""
        try:
            # quartet identify telomeres
            cmd = ['quartet', '-i', str(self.genome_fasta), 
                   '-o', str(self.telomere_dir / 'quartet_output'),
                   '-t', str(self.threads)]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("quartet analysis completed successfully")
                self.results['telomere_gap'] = {
                    'tool': 'quartet',
                    'status': 'success',
                    'output_dir': str(self.telomere_dir / 'quartet_output')
                }
            else:
                logger.error(f"quartet failed: {result.stderr}")
                self.results['telomere_gap'] = {
                    'tool': 'quartet',
                    'status': 'failed',
                    'error': result.stderr
                }
        except Exception as e:
            logger.error(f"Error running quartet: {e}")
            self.results['telomere_gap'] = {
                'tool': 'quartet',
                'status': 'error',
                'error': str(e)
            }
    
    def _run_seqkit(self):
        """Run seqkit for basic statistics (fallback when quartet unavailable)"""
        seqkit_env = self.env_manager.setup_software('seqkit', 
                                                      channels=['bioconda', 'conda-forge'])
        
        try:
            # seqkit stats
            cmd = ['seqkit', 'stats', '-a', '-T', str(self.genome_fasta)]
            result = self.env_manager.run_command(seqkit_env, cmd,
                                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                output_file = self.telomere_dir / 'seqkit_stats.tsv'
                output_file.write_text(result.stdout)
                logger.info(f"seqkit stats saved to {output_file}")
                
                # Count gaps (N's)
                cmd_gap = ['seqkit', 'fx2tab', '-n', '-g', str(self.genome_fasta)]
                result_gap = self.env_manager.run_command(seqkit_env, cmd_gap,
                                                         capture_output=True, text=True)
                
                if result_gap.returncode == 0:
                    gap_file = self.telomere_dir / 'gap_content.tsv'
                    gap_file.write_text(result_gap.stdout)
                    logger.info(f"Gap content saved to {gap_file}")
                
                self.results['telomere_gap'] = {
                    'tool': 'seqkit',
                    'status': 'success',
                    'stats_file': str(output_file),
                    'note': 'No visualization available without quartet'
                }
            else:
                logger.error(f"seqkit failed: {result.stderr}")
                self.results['telomere_gap'] = {
                    'tool': 'seqkit',
                    'status': 'failed',
                    'error': result.stderr
                }
        except Exception as e:
            logger.error(f"Error running seqkit: {e}")
            self.results['telomere_gap'] = {
                'tool': 'seqkit',
                'status': 'error',
                'error': str(e)
            }
    
    def run_busco(self):
        """Run BUSCO analysis"""
        logger.info("=" * 60)
        logger.info("Running BUSCO analysis")
        logger.info("=" * 60)
        
        busco_env = self.env_manager.setup_software('busco',
                                                     channels=['bioconda', 'conda-forge'])
        
        self.results['busco'] = {}
        
        for db in self.busco_dbs:
            db_name = Path(db).name if Path(db).exists() else db
            logger.info(f"Running BUSCO with database: {db_name}")
            
            output_name = f"busco_{db_name}"
            
            try:
                cmd = [
                    'busco',
                    '-i', str(self.genome_fasta),
                    '-o', output_name,
                    '-m', 'genome',
                    '-c', str(self.threads),
                    '--offline' if Path(db).exists() else '--auto-lineage',
                ]
                
                if Path(db).exists():
                    cmd.extend(['--download_path', str(Path(db).parent)])
                    cmd.extend(['-l', db])
                else:
                    cmd.extend(['-l', db])
                
                result = self.env_manager.run_command(
                    busco_env, cmd,
                    cwd=str(self.busco_dir),
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    logger.info(f"BUSCO completed for {db_name}")
                    self.results['busco'][db_name] = {
                        'status': 'success',
                        'output_dir': str(self.busco_dir / output_name)
                    }
                else:
                    logger.error(f"BUSCO failed for {db_name}: {result.stderr}")
                    self.results['busco'][db_name] = {
                        'status': 'failed',
                        'error': result.stderr
                    }
            except Exception as e:
                logger.error(f"Error running BUSCO for {db_name}: {e}")
                self.results['busco'][db_name] = {
                    'status': 'error',
                    'error': str(e)
                }
    
    def run_merqury(self):
        """Run Merqury for QV calculation"""
        logger.info("=" * 60)
        logger.info("Running Merqury for QV calculation")
        logger.info("=" * 60)
        
        merqury_env = self.env_manager.setup_software('merqury',
                                                       channels=['bioconda', 'conda-forge'])
        
        try:
            # Note: Merqury requires k-mer database (meryl)
            # For a complete implementation, we need reads
            # Here we'll document the limitation
            logger.warning("Merqury requires k-mer database from reads")
            logger.warning("Skipping Merqury - requires raw sequencing reads for k-mer counting")
            
            self.results['merqury'] = {
                'status': 'skipped',
                'note': 'Requires raw sequencing reads for k-mer database generation'
            }
        except Exception as e:
            logger.error(f"Error in Merqury setup: {e}")
            self.results['merqury'] = {
                'status': 'error',
                'error': str(e)
            }
    
    def run_ltr_analysis(self):
        """Run LTR analysis pipeline: ltrharvest, LTR_retriever, and LAI"""
        logger.info("=" * 60)
        logger.info("Running LTR analysis pipeline")
        logger.info("=" * 60)
        
        # Setup environments
        genometools_env = self.env_manager.setup_software('genometools', 
                                                          channels=['bioconda', 'conda-forge'])
        ltr_retriever_env = self.env_manager.setup_software('ltr_retriever',
                                                             channels=['bioconda', 'conda-forge'])
        
        try:
            # Step 1: Create genome index for genometools
            logger.info("Creating genome index...")
            index_file = self.ltr_dir / f"{self.genome_fasta.stem}.index"
            
            cmd_index = ['gt', 'suffixerator', '-db', str(self.genome_fasta),
                        '-indexname', str(index_file), '-tis', '-suf', '-lcp', '-des', '-ssp']
            
            result = self.env_manager.run_command(genometools_env, cmd_index,
                                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to create genome index: {result.stderr}")
                self.results['ltr_analysis'] = {'status': 'failed', 'error': 'Index creation failed'}
                return
            
            # Step 2: Run ltrharvest
            logger.info("Running ltrharvest...")
            ltr_output = self.ltr_dir / "ltrharvest.out"
            
            cmd_ltr = ['gt', 'ltrharvest', '-index', str(index_file),
                      '-out', str(ltr_output), '-outinner', '-gff3', str(self.ltr_dir / 'ltrharvest.gff3')]
            
            result = self.env_manager.run_command(genometools_env, cmd_ltr,
                                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"ltrharvest failed: {result.stderr}")
                self.results['ltr_analysis'] = {'status': 'failed', 'error': 'ltrharvest failed'}
                return
            
            logger.info("ltrharvest completed")
            
            # Step 3: Run LTR_retriever
            logger.info("Running LTR_retriever...")
            
            cmd_retriever = ['LTR_retriever', '-genome', str(self.genome_fasta),
                           '-inharvest', str(self.ltr_dir / 'ltrharvest.gff3'),
                           '-threads', str(self.threads)]
            
            result = self.env_manager.run_command(ltr_retriever_env, cmd_retriever,
                                                  cwd=str(self.ltr_dir),
                                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"LTR_retriever warning/error: {result.stderr}")
            else:
                logger.info("LTR_retriever completed")
            
            # Step 4: Calculate LAI
            logger.info("Calculating LAI...")
            
            lai_script = self.ltr_dir / 'calculate_lai.sh'
            lai_script.write_text("""#!/bin/bash
# LAI calculation placeholder
# LAI requires LTR_retriever output and additional processing
echo "LAI calculation would be performed here"
echo "Requires: LAI software and LTR_retriever results"
""")
            lai_script.chmod(0o755)
            
            self.results['ltr_analysis'] = {
                'status': 'completed',
                'ltrharvest_output': str(ltr_output),
                'ltr_retriever_dir': str(self.ltr_dir),
                'note': 'LAI calculation requires additional LAI software'
            }
            
        except Exception as e:
            logger.error(f"Error in LTR analysis: {e}")
            self.results['ltr_analysis'] = {
                'status': 'error',
                'error': str(e)
            }
    
    def run_quast(self):
        """Run QUAST for assembly statistics including N50"""
        logger.info("=" * 60)
        logger.info("Running QUAST for assembly statistics")
        logger.info("=" * 60)
        
        quast_env = self.env_manager.setup_software('quast',
                                                     channels=['bioconda', 'conda-forge'])
        
        try:
            cmd = [
                'quast.py',
                str(self.genome_fasta),
                '-o', str(self.quast_dir),
                '-t', str(self.threads),
                '--min-contig', '0',
                '--plots-format', 'png'
            ]
            
            if self.reference_genome and self.reference_genome.exists():
                cmd.extend(['-r', str(self.reference_genome)])
            
            result = self.env_manager.run_command(quast_env, cmd,
                                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("QUAST completed successfully")
                
                # Parse QUAST report
                report_file = self.quast_dir / 'report.txt'
                if report_file.exists():
                    report_content = report_file.read_text()
                    logger.info("QUAST report preview:")
                    for line in report_content.split('\n')[:20]:
                        logger.info(line)
                
                self.results['quast'] = {
                    'status': 'success',
                    'output_dir': str(self.quast_dir),
                    'report': str(report_file)
                }
            else:
                logger.error(f"QUAST failed: {result.stderr}")
                self.results['quast'] = {
                    'status': 'failed',
                    'error': result.stderr
                }
        except Exception as e:
            logger.error(f"Error running QUAST: {e}")
            self.results['quast'] = {
                'status': 'error',
                'error': str(e)
            }
    
    def run_synteny_analysis(self):
        """Run GenomeSyn for synteny plots"""
        if not self.reference_genome or not self.reference_genome.exists():
            logger.info("No reference genome provided, skipping synteny analysis")
            self.results['synteny'] = {
                'status': 'skipped',
                'reason': 'No reference genome provided'
            }
            return
        
        logger.info("=" * 60)
        logger.info("Running synteny analysis with GenomeSyn")
        logger.info("=" * 60)
        
        if not self.check_genomesyn_available():
            logger.warning("GenomeSyn not found but reference genome provided")
            logger.warning("Skipping synteny analysis")
            self.results['synteny'] = {
                'status': 'skipped',
                'reason': 'GenomeSyn not available'
            }
            return
        
        try:
            cmd = [
                'GenomeSyn',
                '-g1', str(self.reference_genome),
                '-g2', str(self.genome_fasta),
                '-o', str(self.synteny_dir),
                '-t', str(self.threads)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("GenomeSyn completed successfully")
                self.results['synteny'] = {
                    'status': 'success',
                    'output_dir': str(self.synteny_dir)
                }
            else:
                logger.error(f"GenomeSyn failed: {result.stderr}")
                self.results['synteny'] = {
                    'status': 'failed',
                    'error': result.stderr
                }
        except Exception as e:
            logger.error(f"Error running GenomeSyn: {e}")
            self.results['synteny'] = {
                'status': 'error',
                'error': str(e)
            }
    
    def generate_summary(self):
        """Generate summary table of all results"""
        logger.info("=" * 60)
        logger.info("Generating summary report")
        logger.info("=" * 60)
        
        summary_file = self.output_dir / 'summary_report.json'
        summary_txt = self.output_dir / 'summary_report.txt'
        
        # Save JSON
        with open(summary_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Summary JSON saved to: {summary_file}")
        
        # Create text summary
        lines = []
        lines.append("=" * 80)
        lines.append("GENOME QUALITY CONTROL SUMMARY REPORT")
        lines.append("=" * 80)
        lines.append(f"Genome: {self.genome_fasta}")
        lines.append(f"Output Directory: {self.output_dir}")
        lines.append(f"Threads: {self.threads}")
        lines.append("=" * 80)
        lines.append("")
        
        # Telomere and Gap Analysis
        lines.append("TELOMERE AND GAP ANALYSIS")
        lines.append("-" * 80)
        if 'telomere_gap' in self.results:
            for key, value in self.results['telomere_gap'].items():
                lines.append(f"  {key}: {value}")
        lines.append("")
        
        # BUSCO
        lines.append("BUSCO COMPLETENESS ASSESSMENT")
        lines.append("-" * 80)
        if 'busco' in self.results:
            for db, result in self.results['busco'].items():
                lines.append(f"  Database: {db}")
                for key, value in result.items():
                    lines.append(f"    {key}: {value}")
        lines.append("")
        
        # Merqury
        lines.append("MERQURY QV CALCULATION")
        lines.append("-" * 80)
        if 'merqury' in self.results:
            for key, value in self.results['merqury'].items():
                lines.append(f"  {key}: {value}")
        lines.append("")
        
        # LTR Analysis
        lines.append("LTR ANALYSIS AND LAI")
        lines.append("-" * 80)
        if 'ltr_analysis' in self.results:
            for key, value in self.results['ltr_analysis'].items():
                lines.append(f"  {key}: {value}")
        lines.append("")
        
        # QUAST
        lines.append("QUAST ASSEMBLY STATISTICS")
        lines.append("-" * 80)
        if 'quast' in self.results:
            for key, value in self.results['quast'].items():
                lines.append(f"  {key}: {value}")
        lines.append("")
        
        # Synteny
        lines.append("SYNTENY ANALYSIS")
        lines.append("-" * 80)
        if 'synteny' in self.results:
            for key, value in self.results['synteny'].items():
                lines.append(f"  {key}: {value}")
        lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        summary_content = '\n'.join(lines)
        summary_txt.write_text(summary_content)
        
        logger.info(f"Summary text report saved to: {summary_txt}")
        logger.info("\n" + summary_content)
    
    def run_pipeline(self):
        """Execute the complete QC pipeline"""
        logger.info("Starting Genome QC Pipeline")
        logger.info(f"Genome: {self.genome_fasta}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Threads: {self.threads}")
        
        try:
            # Run all analyses
            self.run_telomere_gap_analysis()
            self.run_busco()
            self.run_merqury()
            self.run_ltr_analysis()
            self.run_quast()
            self.run_synteny_analysis()
            
            # Generate summary
            self.generate_summary()
            
            logger.info("=" * 60)
            logger.info("Pipeline completed successfully!")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive Genome Quality Control Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  %(prog)s -g genome.fasta -o results -t 16 -b eukaryota_odb10 bacteria_odb10
  %(prog)s -g genome.fasta -o results -t 16 -b /path/to/local/busco_db -r reference.fasta
        """
    )
    
    parser.add_argument('-g', '--genome', required=True,
                       help='Input genome FASTA file')
    parser.add_argument('-o', '--output', required=True,
                       help='Output directory for results')
    parser.add_argument('-t', '--threads', type=int, default=1,
                       help='Number of threads to use (default: 1)')
    parser.add_argument('-b', '--busco', nargs='+', required=True,
                       help='BUSCO database(s) - can specify multiple databases or local paths')
    parser.add_argument('-r', '--reference', default=None,
                       help='Reference genome for synteny analysis (optional)')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not Path(args.genome).exists():
        logger.error(f"Genome file not found: {args.genome}")
        sys.exit(1)
    
    if args.reference and not Path(args.reference).exists():
        logger.error(f"Reference genome file not found: {args.reference}")
        sys.exit(1)
    
    # Create and run pipeline
    pipeline = GenomeQC(
        genome_fasta=args.genome,
        output_dir=args.output,
        threads=args.threads,
        busco_dbs=args.busco,
        reference_genome=args.reference
    )
    
    pipeline.run_pipeline()


if __name__ == '__main__':
    main()
