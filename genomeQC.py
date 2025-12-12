#!/usr/bin/env python3
"""
Genome Quality Control Pipeline
Comprehensive genomic quality assessment using multiple tools including:
- quartet/seqkit: telomere and gap analysis
- BUSCO: completeness assessment
- Merqury: QV calculation
- LTR analysis: ltrharvest, LTR_retriever, LAI
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
import shlex
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PBSJobManager:
    """Manage PBS/Torque job submission and script generation"""
    
    def __init__(self, queue: str = 'high', nodes: int = 1, ppn: int = 60, 
                 walltime: str = '240:00:00', job_prefix: str = 'genomeQC'):
        self.queue = queue
        self.nodes = nodes
        self.ppn = ppn
        self.walltime = walltime
        self.job_prefix = job_prefix
        self.submitted_jobs = {}  # Track submitted job IDs
        
    def generate_pbs_script(self, job_name: str, commands: List[str], 
                           working_dir: str, env_name: Optional[str] = None,
                           dependencies: Optional[List[str]] = None) -> str:
        """
        Generate PBS job script content
        
        Args:
            job_name: Name of the job
            commands: List of commands to execute
            working_dir: Working directory for the job
            env_name: Optional conda/micromamba environment name
            dependencies: Optional list of job IDs this job depends on
            
        Returns:
            PBS script content as string
        """
        script_lines = [
            "#!/bin/bash",
            f"#PBS -N {job_name}",
            f"#PBS -q {self.queue}",
            f"#PBS -l nodes={self.nodes}:ppn={self.ppn}",
            f"#PBS -j oe",
            f"#PBS -l walltime={self.walltime}"
        ]
        
        # Add job dependencies if specified
        if dependencies:
            dep_string = ":".join(dependencies)
            script_lines.append(f"#PBS -W depend=afterok:{dep_string}")
        
        # Add environment setup and logging
        script_lines.extend([
            "",
            "# Source bashrc for environment",
            "source ~/.bashrc",
            "",
            "# Navigate to working directory",
            f"cd {working_dir}",
            "pwd",
            "WD=`pwd`",
            "",
            "# Setup logging",
            "mkdir -p $WD/log",
            "TIME=`date +%m%d_%H%M`",
            f'exec > >(tee -a $WD/log/{job_name}_$TIME.log $WD/log/{job_name}_$TIME.out) 2> >(tee -a $WD/log/{job_name}_$TIME.err $WD/log/{job_name}_$TIME.out >&2)',
            ""
        ])
        
        # Add environment activation if specified
        if env_name:
            script_lines.extend([
                "# Activate conda/micromamba environment",
                f"#micromamba activate {env_name}",
                ""
            ])
        
        # Add actual commands
        script_lines.extend([
            "# Execute commands",
            "echo 'Starting job execution...'",
            "echo 'Job: {}'".format(job_name),
            "echo 'Date: '`date`",
            ""
        ])
        
        script_lines.extend(commands)
        
        # Add completion message
        script_lines.extend([
            "",
            "echo 'Job completed at: '`date`"
        ])
        
        return "\n".join(script_lines)
    
    def write_pbs_script(self, script_content: str, script_path: Path) -> Path:
        """Write PBS script to file"""
        script_path.write_text(script_content)
        script_path.chmod(0o755)  # Make executable
        logger.info(f"PBS script written to: {script_path}")
        return script_path
    
    def submit_job(self, script_path: Path, dry_run: bool = False) -> Optional[str]:
        """
        Submit PBS job
        
        Args:
            script_path: Path to PBS script
            dry_run: If True, don't actually submit, just show what would be done
            
        Returns:
            Job ID if submitted, None if dry run or submission failed
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would submit job: qsub {script_path}")
            return None
        
        try:
            result = subprocess.run(['qsub', str(script_path)],
                                  capture_output=True, text=True, check=True)
            job_id = result.stdout.strip()
            logger.info(f"Job submitted successfully: {job_id}")
            return job_id
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to submit job: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("qsub command not found. PBS/Torque may not be installed.")
            return None


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
            # For module, we need to load it first - properly escape all command parts
            escaped_cmd = ' '.join(shlex.quote(str(arg)) for arg in command)
            module_cmd = f"module load {shlex.quote(env_info['name'])} && {escaped_cmd}"
            full_cmd = ['bash', '-c', module_cmd]
        else:
            full_cmd = command
        
        return subprocess.run(full_cmd, cwd=cwd, **kwargs)


class GenomeQC:
    """Main genome QC pipeline"""
    
    def __init__(self, genome_fasta: str, output_dir: str, threads: int,
                 busco_dbs: List[str], reference_genome: Optional[str] = None,
                 organism_type: str = 'plant', min_telomere_length: int = 50,
                 cluster_mode: bool = False, pbs_queue: str = 'high',
                 pbs_nodes: int = 1, pbs_ppn: int = 60, 
                 pbs_walltime: str = '240:00:00', dry_run: bool = False):
        self.genome_fasta = Path(genome_fasta).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.threads = threads
        self.busco_dbs = busco_dbs
        self.reference_genome = Path(reference_genome).resolve() if reference_genome else None
        self.organism_type = organism_type
        self.min_telomere_length = min_telomere_length
        
        # Cluster mode settings
        self.cluster_mode = cluster_mode
        self.dry_run = dry_run
        
        self.env_manager = EnvironmentManager()
        self.results = {}
        
        # Initialize PBS job manager if in cluster mode
        if cluster_mode:
            self.pbs_manager = PBSJobManager(
                queue=pbs_queue,
                nodes=pbs_nodes,
                ppn=pbs_ppn,
                walltime=pbs_walltime,
                job_prefix='genomeQC'
            )
            self.job_dependencies = {}  # Track job dependencies
        
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
            # Try quartet.py first (the actual command we use)
            result = subprocess.run(['quartet.py', '--help'], 
                                  capture_output=True)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        try:
            # Fallback to checking for 'quartet' command
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
    
    def _create_and_submit_job(self, job_name: str, commands: List[str],
                               working_dir: Path, env_name: Optional[str] = None,
                               dependencies: Optional[List[str]] = None) -> Optional[str]:
        """
        Create PBS script and submit job (or save script in dry run mode)
        
        Args:
            job_name: Name of the job
            commands: List of commands to execute
            working_dir: Working directory for the job
            env_name: Optional environment name
            dependencies: Optional list of job IDs this job depends on
            
        Returns:
            Job ID if submitted, None otherwise
        """
        if not self.cluster_mode:
            return None
        
        # Create PBS scripts directory
        pbs_dir = self.output_dir / "pbs_scripts"
        pbs_dir.mkdir(exist_ok=True)
        
        # Generate script content
        script_content = self.pbs_manager.generate_pbs_script(
            job_name=job_name,
            commands=commands,
            working_dir=str(working_dir),
            env_name=env_name,
            dependencies=dependencies
        )
        
        # Write script to file
        script_path = pbs_dir / f"{job_name}.pbs"
        self.pbs_manager.write_pbs_script(script_content, script_path)
        
        # Submit job (or log in dry run mode)
        job_id = self.pbs_manager.submit_job(script_path, dry_run=self.dry_run)
        
        if job_id:
            self.pbs_manager.submitted_jobs[job_name] = job_id
            
        return job_id
    
    def run_telomere_gap_analysis(self):
        """Run telomere and gap analysis using quartet or seqkit"""
        logger.info("=" * 60)
        logger.info("Running telomere and gap analysis")
        logger.info("=" * 60)
        
        if self.cluster_mode:
            # Generate PBS job for telomere/gap analysis
            genome_prefix = self.genome_fasta.stem
            
            if self.check_quartet_available():
                commands = [
                    f"quartet.py TeloExplorer -i {self.genome_fasta} -c {self.organism_type} -m {self.min_telomere_length} -p {genome_prefix}"
                ]
            else:
                commands = [
                    f"micromamba run -n seqkit seqkit stats -a -T {self.genome_fasta} > seqkit_stats.tsv",
                    f"micromamba run -n seqkit seqkit fx2tab -n -g {self.genome_fasta} > gap_content.tsv"
                ]
            
            job_id = self._create_and_submit_job(
                job_name="TELOMERE_GAP",
                commands=commands,
                working_dir=self.telomere_dir
            )
            
            if job_id:
                self.job_dependencies['telomere_gap'] = job_id
                
            logger.info(f"Telomere/gap analysis job created: {job_id or 'dry-run'}")
            return
        
        # Original direct execution mode
        if self.check_quartet_available():
            logger.info("Using quartet for telomere and gap analysis")
            self._run_quartet()
        else:
            logger.warning("quartet not found, using seqkit (no visualization)")
            self._run_seqkit()
    
    def _run_quartet(self):
        """Run quartet for telomere and gap analysis with visualization"""
        try:
            # Get genome file name without extension for prefix
            genome_prefix = self.genome_fasta.stem
            
            # quartet TeloExplorer with proper parameters
            # Command format: quartet.py TeloExplorer -i input.fa -c organism_type -m min_length -p prefix
            cmd = ['quartet.py', 'TeloExplorer',
                   '-i', str(self.genome_fasta),
                   '-c', self.organism_type,
                   '-m', str(self.min_telomere_length),
                   '-p', genome_prefix]
            
            result = subprocess.run(cmd, cwd=str(self.telomere_dir),
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("quartet TeloExplorer analysis completed successfully")
                logger.info(f"Output prefix: {genome_prefix}")
                self.results['telomere_gap'] = {
                    'tool': 'quartet',
                    'status': 'success',
                    'output_dir': str(self.telomere_dir),
                    'prefix': genome_prefix,
                    'organism_type': self.organism_type,
                    'min_length': self.min_telomere_length
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
        
        if self.cluster_mode:
            # In cluster mode, create a separate job for each BUSCO database
            self.results['busco'] = {}
            
            for db in self.busco_dbs:
                db_path = Path(db)
                is_local = db_path.exists()
                
                if is_local:
                    db_name = db_path.name
                    lineage_name = db_name
                else:
                    db_name = db
                    lineage_name = db
                
                output_name = f"busco_{db_name}"
                
                # Build command
                cmd_parts = [
                    'micromamba run -n busco busco',
                    f'-i {self.genome_fasta}',
                    f'-o {output_name}',
                    '-m genome',
                    f'-c {self.threads}',
                    f'-l {lineage_name}'
                ]
                
                if is_local:
                    cmd_parts.append(f'--download_path {db_path.parent}')
                    cmd_parts.append('--offline')
                elif db in ['auto', 'auto-lineage']:
                    cmd_parts.append('--auto-lineage')
                
                commands = [' '.join(cmd_parts)]
                
                job_id = self._create_and_submit_job(
                    job_name=f"BUSCO_{db_name}",
                    commands=commands,
                    working_dir=self.busco_dir,
                    env_name='busco'
                )
                
                if job_id:
                    self.job_dependencies[f'busco_{db_name}'] = job_id
                
                logger.info(f"BUSCO job for {db_name} created: {job_id or 'dry-run'}")
            
            return
        
        # Original direct execution mode
        busco_env = self.env_manager.setup_software('busco',
                                                     channels=['bioconda', 'conda-forge'])
        
        self.results['busco'] = {}
        
        for db in self.busco_dbs:
            # Handle local vs remote database paths
            db_path = Path(db)
            is_local = db_path.exists()
            
            if is_local:
                # Extract lineage name from path (e.g., /path/to/eukaryota_odb10 -> eukaryota_odb10)
                db_name = db_path.name
                lineage_name = db_name
            else:
                # Remote database, use as-is
                db_name = db
                lineage_name = db
            
            logger.info(f"Running BUSCO with database: {db_name}")
            
            output_name = f"busco_{db_name}"
            
            try:
                cmd = [
                    'busco',
                    '-i', str(self.genome_fasta),
                    '-o', output_name,
                    '-m', 'genome',
                    '-c', str(self.threads),
                    '-l', lineage_name,
                ]
                
                if is_local:
                    # For local databases, specify download path (parent directory) and use offline mode
                    cmd.extend(['--download_path', str(db_path.parent)])
                    cmd.append('--offline')
                else:
                    # For remote databases, use auto-lineage if no specific lineage provided
                    if db in ['auto', 'auto-lineage']:
                        cmd.append('--auto-lineage')
                
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
        """Run LTR analysis pipeline: ltrharvest, LTR_FINDER_parallel, LTR_retriever, and LAI"""
        logger.info("=" * 60)
        logger.info("Running LTR analysis pipeline")
        logger.info("=" * 60)
        
        genome_name = self.genome_fasta.name
        genome_stem = self.genome_fasta.stem
        
        if self.cluster_mode:
            # Create a single job for the entire LTR analysis pipeline
            index_prefix = self.ltr_dir / genome_stem
            harvest_scn = self.ltr_dir / f"{genome_stem}.harvest.scn"
            raw_ltr_scn = self.ltr_dir / f"{genome_name}.rawLTR.scn"
            pass_list = self.ltr_dir / f"{genome_name}.pass.list"
            out_file = self.ltr_dir / f"{genome_name}.out"
            
            commands = [
                "# Step 1: Create genome index",
                f"micromamba run -n genometools gt suffixerator -db {self.genome_fasta} -indexname {index_prefix} -tis -suf -lcp -des -ssp -sds -dna",
                "",
                "# Step 2: Run ltrharvest",
                f"micromamba run -n genometools gt -j {self.threads} ltrharvest -index {index_prefix} -minlenltr 100 -maxlenltr 7000 -mintsd 4 -maxtsd 6 -motif TGCA -motifmis 1 -similar 85 -vic 10 -seed 20 -seqids yes > {harvest_scn}",
                "",
                "# Step 3: Run LTR_FINDER_parallel (if available)",
                f"micromamba run -n ltr_finder LTR_FINDER_parallel -seq {self.genome_fasta} -threads {self.threads} -harvest_out -size 1000000 || echo 'LTR_FINDER_parallel not available or failed'",
                "",
                "# Step 4: Combine harvest and finder results",
                f"cat {harvest_scn} > {raw_ltr_scn}",
                f"if [ -f {genome_name}.finder.combine.scn ]; then cat {genome_name}.finder.combine.scn >> {raw_ltr_scn}; fi",
                f"if [ -f {genome_stem}.finder.combine.scn ]; then cat {genome_stem}.finder.combine.scn >> {raw_ltr_scn}; fi",
                "",
                "# Step 5: Run LTR_retriever",
                f"micromamba run -n ltr_retriever LTR_retriever -genome {self.genome_fasta} -inharvest {raw_ltr_scn} -threads {self.threads}",
                "",
                "# Step 6: Calculate LAI (if LAI software available)",
                f"if command -v LAI &> /dev/null; then",
                f"  LAI -genome {self.genome_fasta} -intact {pass_list} -all {out_file} -t {self.threads} || echo 'LAI calculation failed'",
                f"else",
                f"  echo 'LAI software not available'",
                f"fi"
            ]
            
            job_id = self._create_and_submit_job(
                job_name="LTR_ANALYSIS",
                commands=commands,
                working_dir=self.ltr_dir
            )
            
            if job_id:
                self.job_dependencies['ltr_analysis'] = job_id
            
            logger.info(f"LTR analysis job created: {job_id or 'dry-run'}")
            return
        
        # Original direct execution mode
        # Setup environments
        genometools_env = self.env_manager.setup_software('genometools', 
                                                          channels=['bioconda', 'conda-forge'])
        ltr_retriever_env = self.env_manager.setup_software('ltr_retriever',
                                                             channels=['bioconda', 'conda-forge'])
        ltr_finder_env = self.env_manager.setup_software('ltr_finder',
                                                         channels=['bioconda', 'conda-forge'])
        
        try:
            
            # Step 1: Create genome index for genometools
            logger.info("Creating genome index with gt suffixerator...")
            index_prefix = self.ltr_dir / genome_stem
            
            # gt suffixerator with all required indices
            cmd_index = ['gt', 'suffixerator',
                        '-db', str(self.genome_fasta),
                        '-indexname', str(index_prefix),
                        '-tis', '-suf', '-lcp', '-des', '-ssp', '-sds', '-dna']
            
            result = self.env_manager.run_command(genometools_env, cmd_index,
                                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to create genome index: {result.stderr}")
                self.results['ltr_analysis'] = {'status': 'failed', 'error': 'Index creation failed'}
                return
            
            logger.info("Genome index created successfully")
            
            # Step 2: Run ltrharvest with specific parameters
            logger.info("Running gt ltrharvest...")
            harvest_scn = self.ltr_dir / f"{genome_stem}.harvest.scn"
            
            cmd_ltr = ['gt', '-j', str(self.threads), 'ltrharvest',
                      '-index', str(index_prefix),
                      '-minlenltr', '100',
                      '-maxlenltr', '7000',
                      '-mintsd', '4',
                      '-maxtsd', '6',
                      '-motif', 'TGCA',
                      '-motifmis', '1',
                      '-similar', '85',
                      '-vic', '10',
                      '-seed', '20',
                      '-seqids', 'yes']
            
            result = self.env_manager.run_command(genometools_env, cmd_ltr,
                                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Save output to .scn file
                harvest_scn.write_text(result.stdout)
                logger.info(f"ltrharvest completed, output saved to {harvest_scn}")
            else:
                logger.error(f"ltrharvest failed: {result.stderr}")
                self.results['ltr_analysis'] = {'status': 'failed', 'error': 'ltrharvest failed'}
                return
            
            # Step 3: Run LTR_FINDER_parallel (if available)
            logger.info("Running LTR_FINDER_parallel...")
            
            # LTR_FINDER_parallel typically outputs to {genome_name}.finder.combine.scn
            # But we need to check for various possible output filenames
            finder_scn = None
            possible_finder_files = [
                self.ltr_dir / f"{genome_name}.finder.combine.scn",
                self.ltr_dir / f"{genome_stem}.finder.combine.scn",
                self.ltr_dir / f"{genome_name}.finder.scn"
            ]
            
            # Check if LTR_FINDER_parallel is available
            try:
                cmd_finder = ['LTR_FINDER_parallel',
                            '-seq', str(self.genome_fasta),
                            '-threads', str(self.threads),
                            '-harvest_out',
                            '-size', '1000000']
                
                result = self.env_manager.run_command(ltr_finder_env, cmd_finder,
                                                      cwd=str(self.ltr_dir),
                                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info("LTR_FINDER_parallel completed")
                    # Find which output file was actually created
                    for possible_file in possible_finder_files:
                        if possible_file.exists():
                            finder_scn = possible_file
                            logger.info(f"Found LTR_FINDER output: {finder_scn}")
                            break
                else:
                    logger.warning(f"LTR_FINDER_parallel warning: {result.stderr}")
            except Exception as e:
                logger.warning(f"LTR_FINDER_parallel not available or failed: {e}")
            
            # Step 4: Combine harvest and finder results
            logger.info("Combining LTR results...")
            raw_ltr_scn = self.ltr_dir / f"{genome_name}.rawLTR.scn"
            
            # Combine the two .scn files carefully
            # Read harvest content
            harvest_content = ""
            if harvest_scn.exists():
                harvest_content = harvest_scn.read_text()
            
            # Read finder content if available
            finder_content = ""
            if finder_scn and finder_scn.exists():
                finder_content = finder_scn.read_text()
            
            # Combine contents
            # If both files exist, combine them; otherwise use whichever is available
            if harvest_content and finder_content:
                # Simple concatenation is acceptable for .scn format
                # as LTR_retriever will handle deduplication and validation
                combined_content = harvest_content.rstrip() + "\n" + finder_content
            elif harvest_content:
                combined_content = harvest_content
            elif finder_content:
                combined_content = finder_content
            else:
                logger.warning("No LTR results found from either ltrharvest or LTR_FINDER")
                combined_content = ""
            
            raw_ltr_scn.write_text(combined_content)
            logger.info(f"Combined LTR results saved to {raw_ltr_scn}")
            
            # Step 5: Run LTR_retriever
            logger.info("Running LTR_retriever...")
            
            cmd_retriever = ['LTR_retriever',
                           '-genome', str(self.genome_fasta),
                           '-inharvest', str(raw_ltr_scn),
                           '-threads', str(self.threads)]
            
            result = self.env_manager.run_command(ltr_retriever_env, cmd_retriever,
                                                  cwd=str(self.ltr_dir),
                                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"LTR_retriever warning/error: {result.stderr}")
            else:
                logger.info("LTR_retriever completed")
            
            # Step 6: Calculate LAI (if LAI software is available)
            logger.info("Checking for LAI software...")
            pass_list = self.ltr_dir / f"{genome_name}.pass.list"
            out_file = self.ltr_dir / f"{genome_name}.out"
            
            if pass_list.exists() and out_file.exists():
                try:
                    cmd_lai = ['LAI',
                              '-genome', str(self.genome_fasta),
                              '-intact', str(pass_list),
                              '-all', str(out_file),
                              '-t', str(self.threads)]
                    
                    result = subprocess.run(cmd_lai, cwd=str(self.ltr_dir),
                                          capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        logger.info("LAI calculation completed")
                    else:
                        logger.warning(f"LAI calculation warning: {result.stderr}")
                except Exception as e:
                    logger.warning(f"LAI software not available: {e}")
            else:
                logger.warning("LTR_retriever output files not found, skipping LAI calculation")
            
            self.results['ltr_analysis'] = {
                'status': 'completed',
                'ltrharvest_output': str(harvest_scn),
                'ltr_finder_output': str(finder_scn) if finder_scn and finder_scn.exists() else 'not available',
                'combined_ltr': str(raw_ltr_scn),
                'ltr_retriever_dir': str(self.ltr_dir),
                'lai_status': 'attempted'
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
        
        if self.cluster_mode:
            # Create job for QUAST analysis
            cmd_parts = [
                'micromamba run -n quast quast.py',
                str(self.genome_fasta),
                f'-o {self.quast_dir}',
                f'-t {self.threads}',
                '--min-contig 0',
                '--plots-format png',
                '--large'
            ]
            
            if self.reference_genome and self.reference_genome.exists():
                cmd_parts.append(f'-r {self.reference_genome}')
            
            commands = [' '.join(cmd_parts)]
            
            job_id = self._create_and_submit_job(
                job_name="QUAST",
                commands=commands,
                working_dir=self.quast_dir,
                env_name='quast'
            )
            
            if job_id:
                self.job_dependencies['quast'] = job_id
            
            logger.info(f"QUAST job created: {job_id or 'dry-run'}")
            return
        
        # Original direct execution mode
        quast_env = self.env_manager.setup_software('quast',
                                                     channels=['bioconda', 'conda-forge'])
        
        try:
            cmd = [
                'quast.py',
                str(self.genome_fasta),
                '-o', str(self.quast_dir),
                '-t', str(self.threads),
                '--min-contig', '0',
                '--plots-format', 'png',
                '--large'  # Add --large flag for large genome assemblies
            ]
            
            if self.reference_genome and self.reference_genome.exists():
                cmd.extend(['-r', str(self.reference_genome)])
                logger.info(f"Using reference genome: {self.reference_genome}")
            
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
        
        if self.cluster_mode:
            # Create job for synteny analysis
            commands = [
                f"GenomeSyn -g1 {self.reference_genome} -g2 {self.genome_fasta} -o {self.synteny_dir} -t {self.threads}"
            ]
            
            job_id = self._create_and_submit_job(
                job_name="SYNTENY",
                commands=commands,
                working_dir=self.synteny_dir
            )
            
            if job_id:
                self.job_dependencies['synteny'] = job_id
            
            logger.info(f"Synteny analysis job created: {job_id or 'dry-run'}")
            return
        
        # Original direct execution mode
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
        
        if self.cluster_mode:
            logger.info(f"Cluster Mode: ENABLED")
            logger.info(f"PBS Queue: {self.pbs_manager.queue}")
            logger.info(f"PBS Resources: nodes={self.pbs_manager.nodes}:ppn={self.pbs_manager.ppn}")
            logger.info(f"PBS Walltime: {self.pbs_manager.walltime}")
            if self.dry_run:
                logger.info("DRY RUN MODE: Jobs will not be submitted")
        
        try:
            # Run all analyses
            self.run_telomere_gap_analysis()
            self.run_busco()
            self.run_merqury()
            self.run_ltr_analysis()
            self.run_quast()
            self.run_synteny_analysis()
            
            # Generate summary only in direct execution mode
            if not self.cluster_mode:
                self.generate_summary()
            
            logger.info("=" * 60)
            if self.cluster_mode:
                logger.info("Pipeline job scripts generated successfully!")
                logger.info("Jobs have been submitted to the PBS queue" if not self.dry_run else "Jobs NOT submitted (dry run mode)")
            else:
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
  # Direct execution mode
  %(prog)s -g genome.fasta -o results -t 16 -b eukaryota_odb10 bacteria_odb10
  %(prog)s -g genome.fasta -o results -t 16 -b /path/to/local/busco_db -r reference.fasta -c plant
  %(prog)s -g genome.fasta -o results -t 16 -b eukaryota_odb10 -c plant -m 50
  
  # Cluster mode (PBS/Torque)
  %(prog)s -g genome.fasta -o results -t 60 -b eukaryota_odb10 --cluster --pbs-queue high --pbs-ppn 60
  %(prog)s -g genome.fasta -o results -t 60 -b eukaryota_odb10 --cluster --dry-run
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
    parser.add_argument('-c', '--organism-type', dest='organism_type', default='plant',
                       choices=['plant', 'animal', 'fungi', 'protist'],
                       help='Organism type for quartet telomere analysis (default: plant)')
    parser.add_argument('-m', '--min-telomere-length', dest='min_telomere_length',
                       type=int, default=50,
                       help='Minimum telomere length for quartet analysis (default: 50)')
    
    # Cluster mode arguments
    parser.add_argument('--cluster', action='store_true',
                       help='Enable cluster mode - generate PBS job scripts instead of running directly')
    parser.add_argument('--pbs-queue', dest='pbs_queue', default='high',
                       help='PBS queue name (default: high)')
    parser.add_argument('--pbs-nodes', dest='pbs_nodes', type=int, default=1,
                       help='Number of nodes for PBS jobs (default: 1)')
    parser.add_argument('--pbs-ppn', dest='pbs_ppn', type=int, default=60,
                       help='Processors per node for PBS jobs (default: 60)')
    parser.add_argument('--pbs-walltime', dest='pbs_walltime', default='240:00:00',
                       help='Walltime for PBS jobs (default: 240:00:00)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Generate PBS scripts but do not submit jobs')
    
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
        reference_genome=args.reference,
        organism_type=args.organism_type,
        min_telomere_length=args.min_telomere_length,
        cluster_mode=args.cluster,
        pbs_queue=args.pbs_queue,
        pbs_nodes=args.pbs_nodes,
        pbs_ppn=args.pbs_ppn,
        pbs_walltime=args.pbs_walltime,
        dry_run=args.dry_run
    )
    
    pipeline.run_pipeline()
    
    # In cluster mode, print summary of submitted jobs
    if args.cluster:
        logger.info("=" * 60)
        logger.info("CLUSTER MODE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"PBS scripts generated in: {pipeline.output_dir}/pbs_scripts/")
        if args.dry_run:
            logger.info("DRY RUN MODE - No jobs were submitted")
        else:
            logger.info("Submitted jobs:")
            for job_name, job_id in pipeline.pbs_manager.submitted_jobs.items():
                logger.info(f"  {job_name}: {job_id}")
        logger.info("=" * 60)


if __name__ == '__main__':
    main()
