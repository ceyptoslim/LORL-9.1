# LORL-9.1 Governance Policy
#
# These OPA rules define which actions are permitted in the LORL network.
# In production, the AuditorAgent queries OPA at runtime to verify compliance.
# In development, the same rules are implemented deterministically in Python.

package lorl.governance

# Default deny
default allow = false

# Allow treaty proposals from registered labs
allow if {
    input.action_type == "treaty_proposal"
    input.actor_registered == true
    valid_treaty_terms(input.terms)
}

# Allow agent decisions that have passed CUSTOS policy check
allow if {
    input.action_type == "agent_decision"
    input.custos_allowed == true
    input.confidence >= 0.5
}

# Allow audit queries (read-only, always safe)
allow if {
    input.action_type == "audit_query"
}

# Treaty terms must include a valid revenue_share
valid_treaty_terms(terms) if {
    share := terms.revenue_share
    share >= 0
    share <= 1
}

# Deny if any violation is found
deny contains msg if {
    input.action_type == "treaty_proposal"
    not valid_treaty_terms(input.terms)
    msg := "Treaty terms must include revenue_share between 0 and 1"
}

deny contains msg if {
    input.action_type == "agent_decision"
    input.confidence < 0.5
    msg := "Agent decision confidence below threshold (0.5)"
}

deny contains msg if {
    not input.actor_registered
    msg := "Actor is not a registered lab"
}
