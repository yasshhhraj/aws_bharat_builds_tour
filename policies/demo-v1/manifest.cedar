@id("BASE-PERMIT-REGISTERED")
permit(principal, action, resource)
when {
    resource.owner == principal &&
    context.policyVersion == context.mandatePolicyVersion &&
    context.allowedEffectClasses.contains(resource.effectClass)
};

@id("OWN-001")
forbid(principal, action, resource)
when { context.policyVersion != context.mandatePolicyVersion };

@id("OWN-002")
forbid(principal, action, resource)
when { resource.owner != principal };

@id("OWN-003")
forbid(principal, action, resource)
when { !context.allowedEffectClasses.contains(resource.effectClass) };

@id("OWN-004")
forbid(principal, action, resource)
when {
    (action == Manifest::Action::"confirm_freight_booking" ||
     action == Manifest::Action::"cancel_freight_booking") &&
    !context.preparedActionPresent
};

@id("PROV-001")
forbid(principal, action == Manifest::Action::"create_dispatch_plan", resource)
when { !context.provenanceFactPresent };

@id("PROV-002")
forbid(principal, action == Manifest::Action::"create_dispatch_plan", resource)
when { context.provenanceFactPresent && !context.provenanceFactHashValid };

@id("PROV-003")
forbid(principal, action == Manifest::Action::"create_dispatch_plan", resource)
when {
    context.provenanceFactPresent &&
    context.provenanceFactHashValid &&
    context.attemptedUnit != context.authoritativeUnit
};

@id("PROV-004")
forbid(principal, action == Manifest::Action::"create_dispatch_plan", resource)
when {
    context.provenanceFactPresent &&
    context.provenanceFactHashValid &&
    context.attemptedWeight != context.authoritativeWeight
};

@id("COLD-001")
forbid(principal, action == Manifest::Action::"create_dispatch_plan", resource)
when { context.cargoClass == "perishable" && !context.vehicleMetadataPresent };

@id("COLD-002")
forbid(principal, action == Manifest::Action::"create_dispatch_plan", resource)
when {
    context.cargoClass == "perishable" &&
    context.vehicleMetadataPresent &&
    (!context.vehicleAvailable ||
     !context.vehicleRefrigerated ||
     context.vehicleCapacityKg < context.authoritativeWeight)
};

@id("COLD-003")
forbid(principal, action, resource)
when {
    context.cargoClass == "perishable" &&
    (action == Manifest::Action::"select_carrier_quote" ||
     action == Manifest::Action::"prepare_freight_booking") &&
    !context.carrierMetadataPresent
};

@id("COLD-004")
forbid(principal, action, resource)
when {
    context.cargoClass == "perishable" &&
    (action == Manifest::Action::"select_carrier_quote" ||
     action == Manifest::Action::"prepare_freight_booking") &&
    context.carrierMetadataPresent &&
    (!context.coldChainCertified || !context.laneSupported)
};

@id("SPEND-001")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when {
    context.spendCommittedMinor < 0 ||
    context.spendReservedMinor < 0 ||
    context.approvalThresholdMinor < 0
};

@id("SPEND-002")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.preparedActionPresent && context.preparedCurrency != context.currency };

@id("SPEND-003")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when {
    context.preparedActionPresent &&
    context.spendCommittedMinor + context.spendReservedMinor > context.approvalThresholdMinor &&
    (context.approvalStatus == "none" || context.approvalStatus == "pending_approval")
};

@id("SPEND-005")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approvalStatus == "approved" && context.approvalExpired };

@id("SPEND-006")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approvalStatus == "approved" && !context.approvalActionMatches };

@id("SPEND-007")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approvalStatus == "approved" && !context.approvalStateMatches };

@id("SPEND-008")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approvalStatus == "approved" && !context.approvalPolicyMatches };

@id("SPEND-010")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approvalStatus == "expired" };

@id("SPEND-011")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approvalStatus == "rejected" };

@id("SOD-000")
forbid(principal, action, resource)
when {
    (action == Manifest::Action::"select_carrier_quote" ||
     action == Manifest::Action::"prepare_freight_booking") &&
    context.quoteIssuer == context.principalId
};

@id("SOD-001")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when {
    context.preparedActionPresent &&
    (context.preparedStatus == "pending_approval" ||
     context.preparedStatus == "confirmed" ||
     context.preparedStatus == "cancelled" ||
     context.preparedStatus == "rejected" ||
     context.preparedStatus == "expired")
};

@id("SOD-002")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.preparedActionPresent && !context.actionHashMatches };

@id("SOD-003")
forbid(principal, action == Manifest::Action::"confirm_freight_booking", resource)
when { context.approverConflictsWithPreparer };

@id("SOD-004")
forbid(principal, action == Manifest::Action::"cancel_freight_booking", resource)
when { context.preparedActionPresent && !context.actionHashMatches };

@id("SOD-005")
forbid(principal, action == Manifest::Action::"cancel_freight_booking", resource)
when { context.preparedStatus == "confirmed" };

@id("SOD-006")
permit(principal, action == Manifest::Action::"cancel_freight_booking", resource)
when {
    resource.owner == principal &&
    context.policyVersion == context.mandatePolicyVersion &&
    context.allowedEffectClasses.contains(resource.effectClass) &&
    context.preparedActionPresent &&
    context.actionHashMatches &&
    context.preparedStatus == "cancelled"
};

@id("SOD-007")
permit(principal, action == Manifest::Action::"cancel_freight_booking", resource)
when {
    resource.owner == principal &&
    context.policyVersion == context.mandatePolicyVersion &&
    context.allowedEffectClasses.contains(resource.effectClass) &&
    context.preparedActionPresent &&
    context.actionHashMatches &&
    context.preparedStatus != "confirmed" &&
    context.preparedStatus != "cancelled"
};

@id("PII-001")
forbid(principal, action == Manifest::Action::"write_tracking_outbox", resource)
when { context.containsForbiddenPiiField };

@id("PII-002")
forbid(principal, action == Manifest::Action::"write_tracking_outbox", resource)
when { context.templateId != "TRACKING_UPDATE_V1" };

@id("PII-003")
forbid(principal, action == Manifest::Action::"write_tracking_outbox", resource)
when { !context.syntheticRecipientValid };

@id("PII-004")
forbid(principal, action == Manifest::Action::"write_tracking_outbox", resource)
when { !context.templateVariablesAllowed };

