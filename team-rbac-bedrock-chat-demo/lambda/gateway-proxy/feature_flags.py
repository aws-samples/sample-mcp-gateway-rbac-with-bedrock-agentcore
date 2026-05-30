"""
AppConfig Feature Flag Helper

Reads feature flags from AWS AppConfig at runtime.
Caches configuration to minimize API calls (AppConfig charges per poll).
"""

import json
import os
import boto3
import time

_client = boto3.client('appconfigdata')
_session_token = None
_cached_flags = None
_cache_expiry = 0
CACHE_TTL = 45  # seconds


def get_flags():
    """Get current feature flags from AppConfig. Returns cached value if fresh."""
    global _session_token, _cached_flags, _cache_expiry

    if _cached_flags and time.time() < _cache_expiry:
        return _cached_flags

    try:
        if not _session_token:
            session = _client.start_configuration_session(
                ApplicationIdentifier=os.environ['APPCONFIG_APP'],
                EnvironmentIdentifier=os.environ['APPCONFIG_ENV'],
                ConfigurationProfileIdentifier=os.environ['APPCONFIG_PROFILE'],
                RequiredMinimumPollIntervalInSeconds=15
            )
            _session_token = session['InitialConfigurationToken']

        response = _client.get_latest_configuration(ConfigurationToken=_session_token)
        _session_token = response['NextPollConfigurationToken']

        content = response['Configuration'].read()
        if content:
            _cached_flags = json.loads(content)
            _cache_expiry = time.time() + CACHE_TTL

        return _cached_flags
    except Exception as e:
        print(f"⚠️ AppConfig error: {e}")
        return _cached_flags  # return stale cache on error


def is_enabled(flag_name):
    """Check if a feature flag is enabled."""
    flags = get_flags()
    if not flags:
        return True  # default to enabled if AppConfig unavailable
    values = flags.get('values', {})
    return values.get(flag_name, {}).get('enabled', True)


def is_team_enabled(team_name):
    """Check if a specific team's access is enabled."""
    flag_key = f"{team_name.replace('-', '_')}_access"
    return is_enabled(flag_key)


def is_guardrail_enabled(team_name=None):
    """Check if guardrail is enabled, optionally for a specific team."""
    flags = get_flags()
    if not flags:
        return True
    guardrail = flags.get('values', {}).get('guardrail_enabled', {})
    if not guardrail.get('enabled', True):
        return False
    if team_name:
        teams = guardrail.get('teams', '')
        return team_name in teams.split(',')
    return True
