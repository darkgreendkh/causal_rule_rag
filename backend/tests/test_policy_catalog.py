import json
from pathlib import Path

import pytest

from app.corpus import _read_policy
from app.policy_catalog import make_catalog
from app.rule_engine import evaluate, validate_expression
from app.workflow import check_workflow, repair_workflow


@pytest.fixture(scope="module")
def corpus():
    data = Path(__file__).resolve().parents[2] / "data"
    units = [
        u
        for folder in ("guojia_shebao", "wuhan_shebao")
        for path in (data / folder).rglob("*.txt")
        for u in _read_policy(path, data)[1]
    ]
    matters, rules, actions, coverage = make_catalog(units)
    return {
        "matters": matters,
        "rules": rules,
        "actions": actions,
        "coverage": coverage,
        "units": units,
    }


def test_all_six_policy_categories_have_executable_conditions(corpus):
    matters = {m["id"]: m for m in corpus["matters"]}
    categories = {
        matters[r["matter_id"]]["category"] for r in corpus["rules"] if r["status"] == "active"
    }
    assert {"养老保险", "医疗保险", "失业保险", "工伤保险", "生育保险", "住房公积金"} <= categories
    assert len(matters) >= 40
    for matter in matters.values():
        assert matter["source_unit_ids"]
        assert set(matter["capabilities"]) == {
            "retrievable",
            "checkable",
            "simulatable",
            "repairable",
        }
        assert matter["gaps"]
    for rule in corpus["rules"]:
        if rule["status"] == "active":
            fields = {f["id"] for f in matters[rule["matter_id"]]["fields"]}
            assert not validate_expression(rule["condition"], fields)
            if rule["purpose"] == "condition_check":
                assert evaluate(rule["condition"], {})["status"] == "unknown"


@pytest.mark.parametrize(
    "rule_id,facts,expected",
    [
        ("resident_pension_age", {"age": 15}, "violated"),
        ("resident_pension_age", {"age": 16}, "satisfied"),
        ("unemployment_contributions", {"unemployment_years": 0.5}, "violated"),
        ("unemployment_contributions", {"unemployment_years": 1}, "satisfied"),
        ("maternity_contributions", {"maternity_months": 5}, "violated"),
        ("maternity_contributions", {"maternity_months": 6}, "satisfied"),
        ("medical_no_duplicate", {"duplicate_medical": True}, "violated"),
        (
            "injury_employer_deadline",
            {"injury_applicant": "单位", "injury_days": 31, "extension_confirmed": False},
            "violated",
        ),
        ("housing_deposit_ratio", {"deposit_ratio": 5}, "satisfied"),
        ("housing_deposit_ratio", {"deposit_ratio": 13}, "violated"),
    ],
)
def test_reviewed_rule_boundaries(corpus, rule_id, facts, expected):
    rule = next(r for r in corpus["rules"] if r["id"] == rule_id)
    assert evaluate(rule["condition"], facts)["status"] == expected


def test_external_actions_cannot_manufacture_approval(corpus):
    matters = {m["id"]: m for m in corpus["matters"]}
    for action in corpus["actions"]:
        fields = {f["id"]: f for f in matters[action["matter_id"]]["fields"]}
        if action["kind"] == "external":
            assert all(fields[f]["role"] == "external" for f in action["effects"])
        else:
            assert all(
                fields[f]["role"] == "applicant" and fields[f]["mutable"] for f in action["effects"]
            )
        assert not validate_expression(action["preconditions"], set(fields))


def test_each_category_has_source_backed_multistep_services(corpus):
    matters = {m["id"]: m for m in corpus["matters"]}
    for category in ("养老保险", "医疗保险", "失业保险", "工伤保险", "生育保险", "住房公积金"):
        actions = [a for a in corpus["actions"] if matters[a["matter_id"]]["category"] == category]
        assert len(actions) >= 3
        assert any(a["kind"] == "user" for a in actions)
        assert any(a["kind"] == "external" for a in actions)
    assert len([m for m in matters.values() if m["capabilities"]["simulatable"]]) >= 25


# Hand-entered article examples, not values inferred from the implementation's expressions.
# Each tuple supplies a compliant case and a material change that breaches that article.
ARTICLE_CASES = [
    ("resident_pension_age", {"age": 16}, {"age": 15}),
    (
        "resident_pension_location",
        {
            "pension_at_household": True,
            "hmt_residence_permit": False,
            "hmt_unemployed": False,
            "pension_at_residence": False,
        },
        {"pension_at_household": False},
    ),
    (
        "resident_pension_status",
        {"student": False, "public_employee": False, "employee_pension_covered": False},
        {"student": True},
    ),
    (
        "resident_pension_receipt",
        {
            "age": 60,
            "resident_pension_years": 15,
            "other_pension": False,
            "other_pension_paying": False,
        },
        {"resident_pension_years": 14},
    ),
    (
        "resident_pension_transfer_condition",
        {"household_moved": True, "receiving_pension": False},
        {"receiving_pension": True},
    ),
    ("pension_transfer_not_receiving", {"receiving_pension": False}, {"receiving_pension": True}),
    (
        "pension_transfer_acceptance",
        {
            "sex": "男",
            "age": 49,
            "returning_home": False,
            "official_transfer": False,
            "benefit_location_confirmed": False,
        },
        {"age": 50},
    ),
    ("retirement_flexible_limit", {"flexible_years": 3}, {"flexible_years": 4}),
    ("medical_no_duplicate", {"duplicate_medical": False}, {"duplicate_medical": True}),
    (
        "medical_flex_wait",
        {"medical_paid_months": 6, "following_month_reached": True},
        {"following_month_reached": False},
    ),
    (
        "newborn_free_first_year",
        {"parent_wuhan_medical_paid": True},
        {"parent_wuhan_medical_paid": False},
    ),
    ("newborn_retroactive", {"newborn_registration_days": 90}, {"newborn_registration_days": 91}),
    (
        "medical_abroad_direct",
        {"medical_filing_confirmed": True, "direct_settlement_enabled": True},
        {"direct_settlement_enabled": False},
    ),
    ("medical_foreign_excluded", {"medical_overseas": False}, {"medical_overseas": True}),
    (
        "medical_account_exclusions",
        {"public_health": False, "fitness_wellness": False, "excluded_medical_item": False},
        {"fitness_wellness": True},
    ),
    (
        "aid_after_insurance",
        {
            "basic_medical_settled": True,
            "serious_medical_settled": True,
            "aid_identity_confirmed": True,
        },
        {"basic_medical_settled": False},
    ),
    ("unemployment_contributions", {"unemployment_years": 1}, {"unemployment_years": 0.9}),
    (
        "unemployment_other_conditions",
        {"involuntary_unemployment": True, "unemployment_registered": True, "seeking_work": True},
        {"involuntary_unemployment": False},
    ),
    (
        "unemployment_self_business",
        {"receiving_unemployment": True, "self_employment_proof": True},
        {"self_employment_proof": False},
    ),
    (
        "unemployment_training_certificate",
        {"qualification_certificate": True, "skill_certificate": False},
        {"qualification_certificate": False},
    ),
    (
        "injury_employer_deadline",
        {"injury_applicant": "单位", "injury_days": 30, "extension_confirmed": False},
        {"injury_days": 31},
    ),
    (
        "injury_individual_deadline",
        {"injury_applicant": "职工", "employer_did_not_apply": True, "within_injury_year": True},
        {"within_injury_year": False},
    ),
    (
        "injury_materials",
        {"injury_application_form": True, "employment_proof": True, "diagnosis_proof": True},
        {"diagnosis_proof": False},
    ),
    (
        "injury_no_exclusion",
        {"intentional_crime": False, "intoxication_drugs": False, "self_harm": False},
        {"self_harm": True},
    ),
    (
        "injury_assessment_materials",
        {
            "injury_decision_confirmed": True,
            "complete_medical_records": True,
            "identity_document": True,
            "committee_other_materials_confirmed": True,
        },
        {"identity_document": False},
    ),
    (
        "injury_reassessment_deadline",
        {"assessment_delivery_days": 15},
        {"assessment_delivery_days": 16},
    ),
    (
        "injury_travel_authorization",
        {"agreement_provider_opinion": True, "injury_travel_approved": True},
        {"injury_travel_approved": False},
    ),
    ("maternity_contributions", {"maternity_months": 6}, {"maternity_months": 5}),
    ("maternity_allowance_contributions", {"maternity_months": 6}, {"maternity_months": 5}),
    ("maternity_medical_contributions", {"maternity_months": 6}, {"maternity_months": 5}),
    ("maternity_nursing_contributions", {"maternity_months": 6}, {"maternity_months": 5}),
    (
        "maternity_nursing_legal_birth",
        {"lawful_birth_confirmed": True},
        {"lawful_birth_confirmed": False},
    ),
    (
        "maternity_medical_provider",
        {
            "designated_maternity_provider": True,
            "emergency_rescue": False,
            "transfer_approved": False,
        },
        {"designated_maternity_provider": False},
    ),
    (
        "maternity_claim_record",
        {"maternity_medical_records": True},
        {"maternity_medical_records": False},
    ),
    (
        "pregnancy_night_work",
        {"pregnancy_weeks": 28, "night_shift": False, "overtime": False},
        {"night_shift": True},
    ),
    ("housing_deposit_ratio", {"deposit_ratio": 12}, {"deposit_ratio": 12.5}),
    ("housing_ratio_equal", {"unit_ratio": 5, "personal_ratio": 5}, {"personal_ratio": 6}),
    (
        "housing_rent_condition",
        {"no_owned_housing": True, "public_rental_qualified": False},
        {"no_owned_housing": False},
    ),
    (
        "housing_rent_exclusion",
        {"outstanding_housing_loan": False, "purchase_withdraw_this_year": False},
        {"purchase_withdraw_this_year": True},
    ),
    (
        "housing_exit_sealed",
        {"employment_terminated": True, "wuhan_household": True, "sealed_months": 24},
        {"sealed_months": 23},
    ),
    ("housing_elevator_filing", {"elevator_filed": True}, {"elevator_filed": False}),
    ("housing_elevator_time", {"elevator_expense_months": 36}, {"elevator_expense_months": 37}),
    (
        "housing_new_loan_contributions",
        {"housing_paid_months": 6, "housing_account_normal": True},
        {"housing_paid_months": 5},
    ),
    (
        "housing_existing_relative",
        {"direct_relative_transaction": False},
        {"direct_relative_transaction": True},
    ),
    (
        "housing_foreign_contributions",
        {"unit_employee": True, "outside_wuhan_deposit": True, "housing_paid_months": 6},
        {"unit_employee": False},
    ),
    (
        "housing_foreign_no_parallel",
        {"parallel_housing_application": False},
        {"parallel_housing_application": True},
    ),
    (
        "flex_housing_pension_months",
        {"flex_pension_months": 6, "flex_elapsed_months": 6},
        {"flex_elapsed_months": 5},
    ),
    (
        "flex_housing_partial",
        {"deposit_method": "自由缴存", "outstanding_housing_loan": False},
        {"deposit_method": "一次性缴存"},
    ),
    (
        "flex_housing_balance",
        {"housing_balance": 30000, "requested_loan": 1000000},
        {"housing_balance": 29999},
    ),
    (
        "shared_cancel_paid",
        {"insurance_arrears_paid": True, "late_fees_paid": True, "fines_paid": True},
        {"late_fees_paid": False},
    ),
]

LOAN_FACTS = {
    "age": 30,
    "loan_identity_valid": True,
    "loan_full_civil_capacity": True,
    "loan_retirement_boundary_confirmed": True,
    "loan_credit_authorized": True,
    "loan_credit_standard_confirmed": True,
    "loan_stable_income": True,
    "loan_repayment_capacity_confirmed": True,
    "outstanding_housing_loan": False,
    "loan_impairing_debt": False,
    "loan_contract_months": 6,
    "loan_downpayment_standard_confirmed": True,
    "loan_housing_record_confirmed": True,
    "loan_guarantee_agreed": True,
    "loan_other_regulations_confirmed": True,
    "housing_paid_months": 6,
    "housing_account_normal": True,
    "housing_balance": 6000,
    "housing_monthly_deposit": 1000,
    "loan_property_type": "存量房",
    "loan_house_age": 30,
    "loan_title_clear": True,
    "loan_residence_right": False,
    "loan_full_ownership": True,
    "loan_already_transferred": False,
    "loan_trade_permitted": True,
    "loan_related_fraud": False,
    "sex": "男",
    "flex_account_months": 13,
    "flex_agreement_complied": True,
    "flex_withdrawn_last_year": False,
    "requested_loan": 200000,
}
ARTICLE_CASES.extend(
    [
        ("housing_new_loan_eligibility", LOAN_FACTS, {"loan_contract_months": 13}),
        ("housing_existing_loan_eligibility", LOAN_FACTS, {"loan_house_age": 31}),
        ("housing_foreign_loan_eligibility", LOAN_FACTS, {"loan_already_transferred": True}),
        ("flex_housing_loan_eligibility", LOAN_FACTS, {"flex_account_months": 12}),
    ]
)


@pytest.mark.parametrize("rule_id,passing,breach", ARTICLE_CASES, ids=[c[0] for c in ARTICLE_CASES])
def test_each_reviewed_article_has_three_valued_source_example(corpus, rule_id, passing, breach):
    rule = next(r for r in corpus["rules"] if r["id"] == rule_id)
    assert rule["evidence"][0]["quote"]
    assert evaluate(rule["condition"], passing)["status"] == "satisfied"
    assert evaluate(rule["condition"], passing | breach)["status"] == "violated"
    assert evaluate(rule["condition"], {})["status"] == "unknown"


def test_every_condition_check_has_a_handwritten_article_example(corpus):
    covered = {c[0] for c in ARTICLE_CASES}
    assert {r["id"] for r in corpus["rules"] if r["purpose"] == "condition_check"} == covered


@pytest.mark.parametrize(
    "rule_id,facts",
    [
        ("pension_transfer_acceptance", {"sex": "女", "age": 39}),
        (
            "resident_pension_location",
            {"hmt_residence_permit": True, "hmt_unemployed": True, "pension_at_residence": True},
        ),
        ("pension_transfer_acceptance", {"returning_home": True}),
        ("pension_transfer_acceptance", {"official_transfer": True}),
        ("pension_transfer_acceptance", {"benefit_location_confirmed": True}),
        ("unemployment_training_certificate", {"skill_certificate": True}),
        (
            "injury_employer_deadline",
            {"injury_applicant": "单位", "injury_days": 31, "extension_confirmed": True},
        ),
        ("injury_employer_deadline", {"injury_applicant": "近亲属"}),
        ("injury_individual_deadline", {"injury_applicant": "单位"}),
        ("maternity_medical_provider", {"emergency_rescue": True}),
        ("maternity_medical_provider", {"transfer_approved": True}),
        ("pregnancy_night_work", {"pregnancy_weeks": 27, "night_shift": True}),
        ("housing_rent_condition", {"public_rental_qualified": True}),
        (
            "housing_exit_sealed",
            {"employment_terminated": True, "wuhan_household": False, "sealed_months": 6},
        ),
    ],
)
def test_article_exception_and_alternative_branches(corpus, rule_id, facts):
    rule = next(r for r in corpus["rules"] if r["id"] == rule_id)
    assert evaluate(rule["condition"], facts)["status"] == "satisfied"


SERVICE_CASES = [
    (
        "resident_pension_enroll",
        ["apply", "registered"],
        {
            "age": 16,
            "student": False,
            "public_employee": False,
            "employee_pension_covered": False,
            "registration_identity_valid": True,
            "pension_at_household": True,
            "resident_pension_enroll_apply_documents": ["有效身份证件"],
            "resident_pension_enroll_registered_confirmed": True,
        },
        "registration_identity_valid",
    ),
    (
        "medical_abroad",
        ["filing", "filed", "settled"],
        {
            "outside_designated_need": True,
            "medical_abroad_filed_confirmed": True,
            "medical_filing_confirmed": True,
            "direct_settlement_enabled": True,
            "medical_abroad_settled_confirmed": True,
        },
        "outside_designated_need",
    ),
    (
        "unemployment_register",
        ["termination_proof", "register", "registered"],
        {
            "unemployment_register_termination_proof_confirmed": True,
            "unemployment_register_register_documents": ["终止或者解除劳动关系的证明"],
            "unemployment_register_registered_confirmed": True,
        },
        "unemployment_register_termination_proof_confirmed",
    ),
    (
        "injury_recognition",
        ["prepare", "apply", "accepted", "decided"],
        {
            "injury_recognition_prepare_documents": [
                "劳动、人事关系证明材料",
                "医疗诊断或职业病诊断证明",
            ],
            "injury_applicant": "职工",
            "employer_did_not_apply": True,
            "within_injury_year": True,
            "employment_proof": True,
            "diagnosis_proof": True,
            "injury_jurisdiction": True,
            "injury_recognition_accepted_confirmed": True,
            "injury_recognition_decided_confirmed": True,
        },
        "within_injury_year",
    ),
    (
        "maternity_allowance",
        ["prepare", "submit", "decided"],
        {
            "maternity_allowance_prepare_documents": ["病历资料"],
            "maternity_insured": True,
            "maternity_medical_records": True,
            "maternity_allowance_decided_confirmed": True,
            "maternity_months": 6,
        },
        "maternity_insured",
    ),
    (
        "flex_housing_enroll",
        ["agreement", "apply", "opened"],
        {
            "flex_single_account": True,
            "flex_pension_months": 6,
            "flex_elapsed_months": 6,
            "flex_housing_enroll_opened_confirmed": True,
        },
        "flex_single_account",
    ),
]


@pytest.mark.parametrize(
    "matter,steps,facts,required", SERVICE_CASES, ids=[c[0] for c in SERVICE_CASES]
)
def test_six_real_services_check_and_repair_from_source_examples(
    corpus, matter, steps, facts, required
):
    ids = [matter + "_" + step for step in steps]
    request = {
        "matter_id": matter,
        "region": "武汉",
        "as_of": "2024-06-01",
        "steps": ids,
        "goal": ids[-1],
        "facts": facts,
    }
    assert check_workflow(corpus, request)["status"] == "satisfied"
    assert (
        check_workflow(corpus, request | {"facts": facts | {required: False}})["status"]
        == "violated"
    )
    missing = {key: value for key, value in facts.items() if key != required}
    assert check_workflow(corpus, request | {"facts": missing})["status"] == "unknown"
    result = repair_workflow(corpus, request | {"steps": ids[1:]})
    assert result["status"] == "repaired"
    assert result["steps"] == ids
    assert result["cost"] == 1
    assert result["checked"]["status"] == "satisfied"


def test_changed_source_does_not_reactivate_the_reviewed_old_threshold(tmp_path):
    from app.corpus import build_corpus

    data = Path(__file__).resolve().parents[2] / "data"
    original = next((data / "wuhan_shebao").glob("01_*.txt"))
    copied = tmp_path / "wuhan_shebao" / original.name
    copied.parent.mkdir()
    copied.write_bytes(original.read_bytes())
    before = build_corpus(tmp_path)
    assert (
        next(r for r in before["rules"] if r["id"] == "resident_pension_age")["status"] == "active"
    )
    copied.write_text(copied.read_text(encoding="utf-8").replace("１６", "１８"), encoding="utf-8")
    after = build_corpus(tmp_path)
    rule = next(r for r in after["rules"] if r["id"] == "resident_pension_age")
    assert "１８" in rule["evidence"][0]["quote"]
    assert rule["status"] == "candidate"
    assert rule["review_source"] == "source_changed_requires_review"
    assert rule["validation_errors"]
    matter = next(m for m in after["matters"] if m["id"] == "resident_pension_enroll")
    assert matter["capabilities"] == {
        "retrievable": True,
        "checkable": False,
        "simulatable": False,
        "repairable": False,
    }
    changed_actions = [a for a in after["actions"] if a["matter_id"] == "resident_pension_transfer"]
    assert changed_actions and all(a["status"] == "candidate" for a in changed_actions)
    result = check_workflow(
        after,
        {
            "matter_id": "resident_pension_enroll",
            "region": "武汉",
            "as_of": "2024-06-01",
            "facts": {"age": 17},
            "steps": [],
        },
    )
    assert result["status"] == "unknown"


def test_source_review_manifest_covers_exactly_the_36_policy_versions(corpus):
    from hashlib import sha256

    data = Path(__file__).resolve().parents[2] / "data"
    path = Path(__file__).resolve().parents[1] / "app/research_data/source_review_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    sources = {u["source_path"] for u in corpus["units"]}
    assert len(manifest["sources"]) == 36
    assert set(manifest["sources"]) == sources
    assert all(
        manifest["sources"][source] == sha256((data / source).read_bytes()).hexdigest()
        for source in sources
    )
