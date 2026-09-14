// Compile and execute the hardening primitives independently before they are
// threaded through each transport call site. This keeps the stacked PR small
// while making every policy primitive executable rather than documentation-only.
#[path = "../src/hardening.rs"]
mod hardening;

#[test]
fn hardening_contract_module_is_executable() {
    let budget = hardening::RecoveryBudget::new(std::time::Duration::from_secs(1));
    assert!(!budget.exhausted());
    assert!(
        budget.child_timeout(std::time::Duration::from_secs(30))
            <= std::time::Duration::from_secs(1)
    );
}
