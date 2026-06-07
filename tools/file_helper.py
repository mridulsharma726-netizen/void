import os
import shutil
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("void.file_helper")

def get_common_roots() -> Dict[str, Path]:
    """Retrieve paths to common user folders on Windows, respecting OneDrive overrides."""
    user_profile = Path(os.environ.get("USERPROFILE", "C:\\"))
    
    desktop = user_profile / "Desktop"
    documents = user_profile / "Documents"
    downloads = user_profile / "Downloads"
    
    # Auto-detect OneDrive directories
    onedrive = user_profile / "OneDrive"
    if onedrive.exists():
        if (onedrive / "Desktop").exists():
            desktop = onedrive / "Desktop"
        if (onedrive / "Documents").exists():
            documents = onedrive / "Documents"
        if (onedrive / "Downloads").exists():
            downloads = onedrive / "Downloads"
            
    return {
        "desktop": desktop,
        "documents": documents,
        "downloads": downloads,
        "workspace": Path(__file__).parent.parent
    }

def find_files(query: str, search_root: str = None) -> Dict[str, Any]:
    """
    Search recursively for files matching a case-insensitive query string.
    Searches common user folders if search_root is not provided.
    """
    query_lower = query.lower().strip()
    found_files = []
    
    roots_to_search = {}
    if search_root:
        root_path = Path(search_root)
        if root_path.exists():
            roots_to_search = {"custom": root_path}
        else:
            return {"status": "error", "message": f"Search directory '{search_root}' does not exist, Sir."}
    else:
        roots_to_search = get_common_roots()
        
    try:
        for name, path in roots_to_search.items():
            logger.info(f"Scanning root: {path}")
            # Walk and search
            for root, dirs, files in os.walk(path):
                # Prune node_modules or standard hidden directories to remain fast
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "venv"]]
                
                for f in files:
                    if query_lower in f.lower():
                        full_path = Path(root) / f
                        found_files.append({
                            "name": f,
                            "path": str(full_path),
                            "size_bytes": full_path.stat().st_size if full_path.exists() else 0,
                            "location": name
                        })
                        if len(found_files) >= 50:  # Cap at 50 matches for safety
                            break
                if len(found_files) >= 50:
                    break
                    
        if found_files:
            summary = "\n".join([f"- **{f['name']}** in {f['location']} (`{f['path']}`)" for f in found_files[:10]])
            if len(found_files) > 10:
                summary += f"\n*...and {len(found_files) - 10} more files found, Sir.*"
            return {
                "status": "ok",
                "message": f"I found **{len(found_files)} files** matching '{query}':\n\n{summary}",
                "data": found_files
            }
        else:
            return {"status": "ok", "message": f"I couldn't find any files matching '{query}', Sir. I checked your Desktop, Documents, Downloads, and workspace folders."}
            
    except Exception as e:
        logger.error(f"File search failed: {e}", exc_info=True)
        return {"status": "error", "message": f"File search failed: {str(e)}"}

def move_files(source_dir: str, target_dir: str, extension_pattern: str = None) -> Dict[str, Any]:
    """
    Move files matching a pattern or extension from source_dir to target_dir.
    Example: move all screenshots (or png files) from Downloads to Desktop.
    """
    common_roots = get_common_roots()
    
    # Resolve source path
    src_path = Path(source_dir)
    if not src_path.exists():
        # Try finding in common roots
        resolved = False
        for path in common_roots.values():
            if (path / source_dir).exists():
                src_path = path / source_dir
                resolved = True
                break
        if not resolved:
            return {"status": "error", "message": f"Source folder '{source_dir}' could not be located."}
            
    # Resolve target path
    tgt_path = Path(target_dir)
    if not tgt_path.exists():
        # Try in common roots or create it
        resolved = False
        for path in common_roots.values():
            if path.name.lower() == target_dir.lower():
                tgt_path = path
                resolved = True
                break
        if not resolved:
            # Create it
            try:
                tgt_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return {"status": "error", "message": f"Could not create target directory '{target_dir}': {e}"}

    moved_files = []
    try:
        for f in os.listdir(src_path):
            file_path = src_path / f
            if file_path.is_file():
                match = True
                if extension_pattern:
                    match = f.lower().endswith(extension_pattern.lower()) or extension_pattern.lower() in f.lower()
                
                if match:
                    shutil.move(str(file_path), str(tgt_path / f))
                    moved_files.append(f)
                    
        if moved_files:
            summary = ", ".join([f"`{f}`" for f in moved_files[:10]])
            if len(moved_files) > 10:
                summary += f" and {len(moved_files) - 10} others"
            return {
                "status": "ok",
                "message": f"Successfully moved **{len(moved_files)} files** to **{tgt_path}**, Sir:\n{summary}"
            }
        else:
            return {"status": "ok", "message": f"No files matching '{extension_pattern or 'all'}' were found in '{src_path}' to move, Sir."}
            
    except Exception as e:
        logger.error(f"Bulk move failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Bulk move failed: {str(e)}"}

def delete_duplicates(folder: str, file_extension: str = None) -> Dict[str, Any]:
    """
    Find and delete duplicate files in a folder based on MD5 checksum hashes.
    """
    common_roots = get_common_roots()
    target_path = Path(folder)
    
    if not target_path.exists():
        resolved = False
        for path in common_roots.values():
            if (path / folder).exists():
                target_path = path / folder
                resolved = True
                break
        if not resolved:
            return {"status": "error", "message": f"Folder '{folder}' could not be located."}

    hashes = {}
    duplicates = []
    deleted_count = 0
    
    try:
        for root, dirs, files in os.walk(target_path):
            for f in files:
                if file_extension and not f.lower().endswith(file_extension.lower()):
                    continue
                    
                full_path = Path(root) / f
                if not full_path.exists():
                    continue
                    
                # Compute MD5
                h = hashlib.md5()
                try:
                    with open(full_path, "rb") as file_bin:
                        # Read 64k chunks
                        for chunk in iter(lambda: file_bin.read(65536), b""):
                            h.update(chunk)
                    file_hash = h.hexdigest()
                    
                    if file_hash in hashes:
                        duplicates.append(full_path)
                    else:
                        hashes[file_hash] = full_path
                except Exception as fe:
                    logger.warning(f"Could not hash file {full_path}: {fe}")
                    
        for dup in duplicates:
            try:
                os.remove(dup)
                deleted_count += 1
            except Exception as de:
                logger.error(f"Failed to delete duplicate {dup}: {de}")
                
        if deleted_count > 0:
            summary_lines = []
            for d in duplicates[:10]:
                try:
                    h_test = hashlib.md5()
                    with open(d, 'rb') as f_bin:
                        for chunk in iter(lambda: f_bin.read(65536), b""):
                            h_test.update(chunk)
                    file_hash = h_test.hexdigest()
                    orig_name = hashes[file_hash].name
                    summary_lines.append(f"- Deleted duplicate `{d.name}` (Original: `{orig_name}`)")
                except:
                    summary_lines.append(f"- Deleted duplicate `{d.name}`")
            summary = "\n".join(summary_lines)
            return {
                "status": "ok",
                "message": f"Cleaned up **{deleted_count} duplicate files** in '{target_path}', Sir. Memory optimization complete."
            }
        else:
            return {"status": "ok", "message": f"I checked '{target_path}' and found no duplicate files, Sir. Everything is clean!"}
            
    except Exception as e:
        logger.error(f"Duplicate cleanup failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Duplicate cleanup failed: {str(e)}"}

def create_folder(folder_path: str) -> Dict[str, Any]:
    """Create a folder dynamically."""
    common_roots = get_common_roots()
    
    target_path = Path(folder_path)
    if not target_path.is_absolute():
        # Default to Desktop if relative
        target_path = common_roots["desktop"] / folder_path
        
    try:
        target_path.mkdir(parents=True, exist_ok=True)
        return {
            "status": "ok",
            "message": f"Successfully created folder: **{target_path}**, Sir. It is ready for use."
        }
    except Exception as e:
        logger.error(f"Folder creation failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Folder creation failed: {str(e)}"}
