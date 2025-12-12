#!/bin/bash
# Installation script for genomeQC pipeline
# This script helps set up the environment for running genomeQC

set -e

echo "=================================="
echo "genomeQC Installation Script"
echo "=================================="
echo ""

# Check if micromamba is installed
if command -v micromamba &> /dev/null; then
    echo "✓ micromamba is installed"
else
    echo "✗ micromamba not found"
    echo "Installing micromamba..."
    
    # Install micromamba
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
        mkdir -p ~/.local/bin
        mv bin/micromamba ~/.local/bin/
        export PATH="$HOME/.local/bin:$PATH"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        echo "✓ micromamba installed to ~/.local/bin/"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        curl -Ls https://micro.mamba.pm/api/micromamba/osx-64/latest | tar -xvj bin/micromamba
        mkdir -p ~/.local/bin
        mv bin/micromamba ~/.local/bin/
        export PATH="$HOME/.local/bin:$PATH"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bash_profile
        echo "✓ micromamba installed to ~/.local/bin/"
    else
        echo "Unsupported OS. Please install micromamba manually."
        exit 1
    fi
fi

echo ""
echo "=================================="
echo "Core Dependencies"
echo "=================================="
echo ""
echo "The pipeline will automatically install the following tools when needed:"
echo "  - seqkit (for genome statistics)"
echo "  - busco (for completeness assessment)"
echo "  - merqury (for QV calculation)"
echo "  - genometools (for LTR analysis)"
echo "  - ltr_retriever (for LTR analysis)"
echo "  - quast (for assembly statistics)"
echo ""
echo "These will be installed via micromamba on first use."
echo ""

# Optional tools warning
echo "=================================="
echo "Optional Tools (Manual Installation)"
echo "=================================="
echo ""
echo "The following tools are NOT managed by micromamba and must be installed separately:"
echo ""
echo "1. quartet - For telomere and gap visualization"
echo "   - If not installed, pipeline will use seqkit (no visualization)"
echo "   - Installation: Follow instructions at quartet repository"
echo ""
echo "2. GenomeSyn - For synteny plot generation"
echo "   - If not installed and reference genome provided, pipeline will skip with warning"
echo "   - Installation: Follow instructions at GenomeSyn repository"
echo ""
echo "3. LAI - For LTR-based Assembly Index calculation"
echo "   - Required for completing LAI analysis after LTR_retriever"
echo "   - Installation: Follow instructions at LAI repository"
echo ""

# Make scripts executable
echo "=================================="
echo "Setting up scripts"
echo "=================================="
chmod +x genomeQC.py
chmod +x example_usage.sh
chmod +x test_pipeline.py
echo "✓ Scripts made executable"
echo ""

# Run tests
echo "=================================="
echo "Running Tests"
echo "=================================="
echo ""
if python3 test_pipeline.py; then
    echo ""
    echo "=================================="
    echo "Installation Complete!"
    echo "=================================="
    echo ""
    echo "Usage:"
    echo "  python genomeQC.py --help"
    echo ""
    echo "Example:"
    echo "  python genomeQC.py -g genome.fasta -o results -t 16 -b eukaryota_odb10"
    echo ""
else
    echo ""
    echo "✗ Tests failed. Please check the error messages above."
    exit 1
fi
