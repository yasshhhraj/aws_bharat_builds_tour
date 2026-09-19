use cedar_policy::{
    Authorizer, Context, Decision, Entities, EntityUid, PolicyId, PolicySet, Request, Schema,
    ValidationMode, Validator,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::io::Read;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::Arc;
use std::time::Instant;
use tiny_http::{Header, Method, Request as HttpRequest, Response, Server, StatusCode};

#[derive(Clone)]
struct AppState {
    authorizer: Arc<Authorizer>,
    policies: Arc<PolicySet>,
    schema: Arc<Schema>,
    policy_version: String,
    bundle_hash: String,
    schema_hash: String,
    cedar_version: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct AuthorizationInput {
    request_id: String,
    principal: String,
    action: String,
    resource: String,
    context: Value,
    entities: Value,
    policy_version: String,
    bundle_hash: String,
}

#[derive(Serialize)]
struct AuthorizationOutput {
    request_id: String,
    decision: String,
    determining_policy_ids: Vec<String>,
    errors: Vec<String>,
    policy_version: String,
    bundle_hash: String,
    evaluation_us: u128,
}

#[derive(Serialize)]
struct HealthOutput {
    status: &'static str,
    engine: &'static str,
    cedar_version: String,
    policy_version: String,
    bundle_hash: String,
    schema_hash: String,
    validation: &'static str,
}

#[derive(Serialize)]
struct ErrorOutput {
    error: ErrorBody,
}

#[derive(Serialize)]
struct ErrorBody {
    code: &'static str,
    message: &'static str,
}

struct Config {
    listen: String,
    schema_path: PathBuf,
    policies_path: PathBuf,
    policy_version: String,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("manifest cedar pdp startup failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let config = parse_args()?;
    if !(config.listen.starts_with("127.0.0.1:") || config.listen.starts_with("localhost:")) {
        return Err("the checkpoint 7 PDP must bind to loopback".to_string());
    }

    let schema_source = fs::read_to_string(&config.schema_path)
        .map_err(|_| "unable to read Cedar schema".to_string())?;
    let policy_source = fs::read_to_string(&config.policies_path)
        .map_err(|_| "unable to read Cedar policies".to_string())?;
    let schema = Schema::from_json_str(&schema_source)
        .map_err(|error| format!("invalid Cedar schema: {error}"))?;
    let policies = load_policies(&policy_source)?;

    let validation = Validator::new(schema.clone()).validate(&policies, ValidationMode::Strict);
    if !validation.validation_passed_without_warnings() {
        let error_count = validation.validation_errors().count();
        let warning_count = validation.validation_warnings().count();
        return Err(format!(
            "Cedar policy validation failed ({error_count} errors, {warning_count} warnings)"
        ));
    }

    let schema_hash = sha256(schema_source.as_bytes());
    let bundle_hash = sha256(
        [
            b"manifest-cedar-bundle-v1\0".as_slice(),
            schema_source.as_bytes(),
            b"\0".as_slice(),
            policy_source.as_bytes(),
        ]
        .concat()
        .as_slice(),
    );
    let state = AppState {
        authorizer: Arc::new(Authorizer::new()),
        policies: Arc::new(policies),
        schema: Arc::new(schema),
        policy_version: config.policy_version,
        bundle_hash,
        schema_hash,
        cedar_version: cedar_policy::get_sdk_version().to_string(),
    };

    let server =
        Server::http(&config.listen).map_err(|_| "unable to bind PDP listener".to_string())?;
    eprintln!("manifest cedar pdp ready on {}", config.listen);
    for request in server.incoming_requests() {
        handle_request(request, &state);
    }
    Ok(())
}

fn load_policies(source: &str) -> Result<PolicySet, String> {
    let parsed =
        PolicySet::from_str(source).map_err(|error| format!("invalid Cedar policy: {error}"))?;
    let mut renamed = Vec::new();
    for policy in parsed.policies() {
        let id = policy
            .annotation("id")
            .ok_or_else(|| "every Cedar policy must have an @id annotation".to_string())?;
        let policy_id =
            PolicyId::from_str(id).map_err(|_| "invalid Cedar policy id".to_string())?;
        renamed.push(policy.new_id(policy_id));
    }
    PolicySet::from_policies(renamed).map_err(|error| format!("invalid Cedar policy set: {error}"))
}

fn parse_args() -> Result<Config, String> {
    let mut listen = "127.0.0.1:8765".to_string();
    let mut schema_path = None;
    let mut policies_path = None;
    let mut policy_version = "demo-v1".to_string();
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        let value = args
            .next()
            .ok_or_else(|| format!("missing value for {arg}"))?;
        match arg.as_str() {
            "--listen" => listen = value,
            "--schema" => schema_path = Some(PathBuf::from(value)),
            "--policies" => policies_path = Some(PathBuf::from(value)),
            "--policy-version" => policy_version = value,
            _ => return Err(format!("unknown argument {arg}")),
        }
    }
    Ok(Config {
        listen,
        schema_path: schema_path.ok_or_else(|| "--schema is required".to_string())?,
        policies_path: policies_path.ok_or_else(|| "--policies is required".to_string())?,
        policy_version,
    })
}

fn handle_request(mut request: HttpRequest, state: &AppState) {
    if request.method() == &Method::Get && request.url() == "/health/ready" {
        let body = HealthOutput {
            status: "ready",
            engine: "cedar",
            cedar_version: state.cedar_version.clone(),
            policy_version: state.policy_version.clone(),
            bundle_hash: state.bundle_hash.clone(),
            schema_hash: state.schema_hash.clone(),
            validation: "passed",
        };
        respond_json(request, StatusCode(200), &body);
        return;
    }
    if request.method() == &Method::Post && request.url() == "/v1/authorize" {
        let content_length = request
            .headers()
            .iter()
            .find(|header| header.field.equiv("Content-Length"))
            .and_then(|header| header.value.as_str().parse::<usize>().ok())
            .unwrap_or(0);
        if content_length == 0 || content_length > 65_536 {
            respond_error(
                request,
                StatusCode(413),
                "REQUEST_SIZE_INVALID",
                "Authorization request size is invalid.",
            );
            return;
        }
        let mut body = String::with_capacity(content_length);
        if request
            .as_reader()
            .take(65_537)
            .read_to_string(&mut body)
            .is_err()
            || body.len() > 65_536
        {
            respond_error(
                request,
                StatusCode(400),
                "REQUEST_READ_FAILED",
                "Authorization request could not be read.",
            );
            return;
        }
        let input: AuthorizationInput = match serde_json::from_str(&body) {
            Ok(value) => value,
            Err(_) => {
                respond_error(
                    request,
                    StatusCode(400),
                    "REQUEST_INVALID",
                    "Authorization request is invalid.",
                );
                return;
            }
        };
        match authorize(input, state) {
            Ok(output) => respond_json(request, StatusCode(200), &output),
            Err(_) => respond_error(
                request,
                StatusCode(422),
                "CEDAR_REQUEST_INVALID",
                "Authorization request does not conform to the Cedar contract.",
            ),
        }
        return;
    }
    respond_error(request, StatusCode(404), "NOT_FOUND", "Route not found.");
}

fn authorize(input: AuthorizationInput, state: &AppState) -> Result<AuthorizationOutput, String> {
    if input.policy_version != state.policy_version || input.bundle_hash != state.bundle_hash {
        return Err("policy identity mismatch".to_string());
    }
    let principal =
        EntityUid::from_str(&input.principal).map_err(|_| "invalid principal".to_string())?;
    let action = EntityUid::from_str(&input.action).map_err(|_| "invalid action".to_string())?;
    let resource =
        EntityUid::from_str(&input.resource).map_err(|_| "invalid resource".to_string())?;
    let context = Context::from_json_value(input.context, Some((&state.schema, &action)))
        .map_err(|_| "invalid context".to_string())?;
    let entities = Entities::from_json_value(input.entities, Some(&state.schema))
        .map_err(|_| "invalid entities".to_string())?;
    let request = Request::new(principal, action, resource, context, Some(&state.schema))
        .map_err(|_| "invalid request".to_string())?;
    let started = Instant::now();
    let response = state
        .authorizer
        .is_authorized(&request, &state.policies, &entities);
    let evaluation_us = started.elapsed().as_micros();
    let mut determining_policy_ids = response
        .diagnostics()
        .reason()
        .map(ToString::to_string)
        .collect::<Vec<_>>();
    determining_policy_ids.sort();
    let errors = response
        .diagnostics()
        .errors()
        .map(|_| "authorization_evaluation_error".to_string())
        .collect::<Vec<_>>();
    Ok(AuthorizationOutput {
        request_id: input.request_id,
        decision: match response.decision() {
            Decision::Allow => "allow".to_string(),
            Decision::Deny => "deny".to_string(),
        },
        determining_policy_ids,
        errors,
        policy_version: state.policy_version.clone(),
        bundle_hash: state.bundle_hash.clone(),
        evaluation_us,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(bytes))
}

fn respond_json<T: Serialize>(request: HttpRequest, status: StatusCode, value: &T) {
    let body = serde_json::to_string(value).unwrap_or_else(|_| "{}".to_string());
    let mut response = Response::from_string(body).with_status_code(status);
    if let Ok(header) = Header::from_bytes("Content-Type", "application/json") {
        response = response.with_header(header);
    }
    let _ = request.respond(response);
}

fn respond_error(
    request: HttpRequest,
    status: StatusCode,
    code: &'static str,
    message: &'static str,
) {
    respond_json(
        request,
        status,
        &ErrorOutput {
            error: ErrorBody { code, message },
        },
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    const SCHEMA: &str = include_str!("../../../policies/schema/manifest.cedarschema.json");
    const POLICIES: &str = include_str!("../../../policies/demo-v1/manifest.cedar");

    #[test]
    fn shipped_bundle_parses_and_strictly_validates() {
        let schema = Schema::from_json_str(SCHEMA).expect("shipped schema must parse");
        let policies = load_policies(POLICIES).expect("shipped policies must parse");
        let validation = Validator::new(schema).validate(&policies, ValidationMode::Strict);
        assert!(validation.validation_passed_without_warnings());
        assert_eq!(policies.policies().count(), 34);
    }

    #[test]
    fn bundle_digest_is_stable_and_domain_separated() {
        let first = sha256(b"manifest-cedar-bundle-v1\0schema\0policies");
        let second = sha256(b"manifest-cedar-bundle-v1\0schema\0policies");
        assert_eq!(first, second);
        assert!(first.starts_with("sha256:"));
        assert_ne!(first, sha256(b"schema\0policies"));
    }
}
