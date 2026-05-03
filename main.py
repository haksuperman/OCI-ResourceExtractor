from log_utils import log_event
import common
from runner import run_inventory


def _select_profile(profiles):
    val = input("\nSelect number: ").strip()
    if val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(profiles):
            return profiles[idx]
        log_event(
            "ERROR",
            "runner",
            "invalid_profile_selection",
            message="Selected profile number is out of range",
            selection=val,
            profile_count=len(profiles),
        )
        return None

    if val in profiles:
        return val

    log_event(
        "ERROR",
        "runner",
        "invalid_profile_selection",
        message="Selected profile name was not found in OCI config",
        selection=val,
    )
    return None


def main():
    profiles = common.get_profiles()
    if not profiles:
        log_event("ERROR", "runner", "profiles_not_found", message="No OCI profiles found")
        return

    print("\n--- Select OCI Profile ---")
    for i, p in enumerate(profiles):
        print(f"{i+1}. {p}")
    
    try:
        selected_profile = _select_profile(profiles)
        if not selected_profile:
            return
        run_inventory(selected_profile)
        
    except Exception as e:
        log_event("ERROR", "runner", "run_exception", detail=str(e))

if __name__ == "__main__":
    main()
