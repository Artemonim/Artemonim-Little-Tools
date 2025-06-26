# Pretrained Models Directory

This directory contains large pretrained model files that are automatically downloaded when MatAnyone is first used.

## Files

-   **matanyone.pth** (~135MB) - MatAnyone model weights
-   **sam_vit_h_4b8939.pth** (~2.4GB) - Segment Anything Model (SAM) weights

## Important Notes

⚠️ **These files are excluded from Git** due to their large size (2.5GB+ total).

✅ **Automatic Download**: The models are automatically downloaded from their official repositories when you first launch MatAnyone:

-   MatAnyone model: Downloaded from GitHub releases
-   SAM model: Downloaded from Facebook's official repository

🔄 **No Manual Setup Required**: The application will handle downloading these files automatically on first run.

## Troubleshooting

If models fail to download automatically:

1. Check your internet connection
2. Ensure you have sufficient disk space (3GB+ free)
3. Check if your firewall/antivirus is blocking the downloads
4. Try running the application again - it will retry the download

## Model Sources

-   **MatAnyone**: https://github.com/pq-yang/MatAnyone/releases
-   **SAM**: https://github.com/facebookresearch/segment-anything
