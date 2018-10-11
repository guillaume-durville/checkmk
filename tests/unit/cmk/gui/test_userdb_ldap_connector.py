#!/usr/bin/env python
# encoding: utf-8

import pytest
from mockldap import MockLdap, LDAPObject

import cmk.gui.plugins.userdb.ldap_connector as ldap
import cmk.gui.plugins.userdb.utils as userdb_utils

def test_connector_info():
    assert ldap.LDAPUserConnector.type() == "ldap"
    assert "LDAP" in ldap.LDAPUserConnector.title()
    assert ldap.LDAPUserConnector.short_title() == "LDAP"


def test_connector_registered():
    assert userdb_utils.user_connector_registry.get("ldap") == ldap.LDAPUserConnector


def test_sync_plugins():
    assert sorted(ldap.ldap_attribute_plugins.keys()) == [
        'alias',
        'auth_expire',
        'email',
        'groups_to_attributes',
        'groups_to_contactgroups',
        'groups_to_roles',
        'pager'
    ]


tree = {
    "dc=org": {
        "objectclass": ["domain"],
        "objectcategory": ["domain"],
        "dn": ["dc=org"],
        "dc": "org",
    },
    "dc=check-mk,dc=org": {
        "objectclass": ["domain"],
        "objectcategory": ["domain"],
        "dn": ["dc=check-mk,dc=org"],
        "dc": "check-mk",
    },
    "ou=users,dc=check-mk,dc=org": {
        "objectclass": ["organizationalUnit"],
        "objectcategory": ["organizationalUnit"],
        "dn": ["ou=users,dc=check-mk,dc=org"],
        "ou": "users",
    },
    "ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["organizationalUnit"],
        "objectcategory": ["organizationalUnit"],
        "dn": ["ou=groups,dc=check-mk,dc=org"],
        "ou": "groups",
    },
    "cn=admin,ou=users,dc=check-mk,dc=org": {
        "objectclass": ["user"],
        "objectcategory": ["person"],
        "dn": ["cn=admin,ou=users,dc=check-mk,dc=org"],
        "cn": ["Admin"],
        "samaccountname": [u"admin"],
        "userPassword": ["ldap-test"],
        "mail": ["admin@check-mk.org"],
    },
    "cn=härry,ou=users,dc=check-mk,dc=org": {
        "objectclass": ["user"],
        "objectcategory": ["person"],
        "dn": ["cn=härry,ou=users,dc=check-mk,dc=org"],
        "cn": ["Härry Hörsch"],
        "samaccountname": ["härry"],
        "userPassword": ["ldap-test"],
        "mail": ["härry@check-mk.org"],
    },
    "cn=sync-user,ou=users,dc=check-mk,dc=org": {
        "objectclass": ["user"],
        "objectcategory": ["person"],
        "dn": ["cn=sync-user,ou=users,dc=check-mk,dc=org"],
        "cn": ["sync-user"],
        "samaccountname": ["sync-user"],
        "userPassword": ["sync-secret"],
    },
    "cn=admins,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=admins,ou=groups,dc=check-mk,dc=org"],
        "cn": ["admins"],
        "member": [
            "cn=admin,ou=users,dc=check-mk,dc=org",
        ],
    },
    "cn=älle,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=älle,ou=groups,dc=check-mk,dc=org"],
        "cn": ["alle"],
        "member": [
            "cn=admin,ou=users,dc=check-mk,dc=org",
            "cn=härry,ou=users,dc=check-mk,dc=org",
        ],
    },
    "cn=top-level,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=top-level,ou=groups,dc=check-mk,dc=org"],
        "cn": ["top-level"],
        "member": [
            "cn=level1,ou=groups,dc=check-mk,dc=org",
            "cn=sync-user,ou=users,dc=check-mk,dc=org",
        ],
    },
    "cn=level1,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=level1,ou=groups,dc=check-mk,dc=org"],
        "cn": ["level1"],
        "member": [
            "cn=level2,ou=groups,dc=check-mk,dc=org",
        ],
    },
    "cn=level2,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=level2,ou=groups,dc=check-mk,dc=org"],
        "cn": ["level2"],
        "member": [
            "cn=admin,ou=users,dc=check-mk,dc=org",
            "cn=härry,ou=users,dc=check-mk,dc=org",
        ],
    },
    "cn=loop1,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=loop1,ou=groups,dc=check-mk,dc=org"],
        "cn": ["loop1"],
        "member": [
            "cn=admin,ou=users,dc=check-mk,dc=org",
            "cn=loop2,ou=groups,dc=check-mk,dc=org",
        ],
    },
    "cn=loop2,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=loop2,ou=groups,dc=check-mk,dc=org"],
        "cn": ["loop2"],
        "member": [
            "cn=loop3,ou=groups,dc=check-mk,dc=org",
        ],
    },
    "cn=loop3,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=loop3,ou=groups,dc=check-mk,dc=org"],
        "cn": ["loop3"],
        "member": [
            "cn=loop1,ou=groups,dc=check-mk,dc=org",
            "cn=härry,ou=users,dc=check-mk,dc=org",
        ],
    },
    "cn=empty,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=empty,ou=groups,dc=check-mk,dc=org"],
        "cn": ["empty"],
        "member": [
        ],
    },
    "cn=member-out-of-scope,ou=groups,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=member-out-of-scope,ou=groups,dc=check-mk,dc=org"],
        "cn": ["member-out-of-scope"],
        "member": [
            "cn=nono,ou=out-of-scope,dc=check-mk,dc=org",
        ],
    },
    "cn=out-of-scope,dc=check-mk,dc=org": {
        "objectclass": ["group"],
        "objectcategory": ["group"],
        "dn": ["cn=out-of-scope,ou=groups,dc=check-mk,dc=org"],
        "cn": ["out-of-scope"],
        "member": [
            "cn=admin,ou=users,dc=check-mk,dc=org",
        ],
    },
}

@pytest.fixture(scope="module")
def mocked_ldap():
    ldap_mock = MockLdap(tree)

    ldap_connection = ldap.LDAPUserConnector({
        "id"   : "default",
        "type" : "ldap",
        "description": "Test connection",
        "disabled": False,
        "cache_livetime": 300,
        "suffix": "testldap",
        "active_plugins": {'email': {}, 'alias': {}, 'auth_expire': {}},
        "directory_type": ("ad", {
            "connect_to": ("fixed_list", {"server": "127.0.0.1"}),
        }),
        "bind": ("cn=sync-user,ou=users,dc=check-mk,dc=org", "sync-secret"),
        "user_id_umlauts": "keep",
        "user_scope": "sub",
        "user_dn": "ou=users,dc=check-mk,dc=org",
        "group_dn": "ou=groups,dc=check-mk,dc=org",
        "group_scope": "sub",
    })

    ldap_connection.disconnect = lambda: None
    ldap_connection.connect = lambda: None
    ldap_mock.start()
    ldap_connection._ldap_obj = ldap_mock["ldap://127.0.0.1"]

    def search_ext(self, base, scope, filterstr='(objectclass=*)', attrlist=None, attrsonly=0, serverctrls=None):
        return self.search(base, scope, filterstr, attrlist, attrsonly)

    LDAPObject.search_ext = search_ext
    LDAPObject.result3 = lambda *args, **kwargs: tuple(list(LDAPObject.result(*args, **kwargs)) + [None, []])

    return ldap_connection


def _check_restored_bind_user(mocked_ldap):
    assert mocked_ldap._ldap_obj.whoami_s() == "dn:cn=sync-user,ou=users,dc=check-mk,dc=org"


def test_check_credentials_success(mocked_ldap):
    result = mocked_ldap.check_credentials("admin", "ldap-test")
    assert isinstance(result, unicode)
    assert result == "admin"

    result = mocked_ldap.check_credentials(u"admin", "ldap-test")
    assert isinstance(result, unicode)
    assert result == "admin"
    _check_restored_bind_user(mocked_ldap)


def test_check_credentials_invalid(mocked_ldap):
    assert mocked_ldap.check_credentials("admin", "WRONG") == False
    _check_restored_bind_user(mocked_ldap)


def test_check_credentials_not_existing(mocked_ldap):
    assert mocked_ldap.check_credentials("john", "secret") == None
    _check_restored_bind_user(mocked_ldap)


def test_check_credentials_enforce_conn_success(mocked_ldap):
    result = mocked_ldap.check_credentials("admin@testldap", "ldap-test")
    assert isinstance(result, unicode)
    assert result == "admin"
    _check_restored_bind_user(mocked_ldap)


def test_check_credentials_enforce_invalid(mocked_ldap):
    assert mocked_ldap.check_credentials("admin@testldap", "WRONG") == False
    _check_restored_bind_user(mocked_ldap)


def test_check_credentials_enforce_not_existing(mocked_ldap):
    assert mocked_ldap.check_credentials("john@testldap", "secret") == False
    _check_restored_bind_user(mocked_ldap)


def test_object_exists(mocked_ldap):
    assert mocked_ldap.object_exists("dc=org") == True
    assert mocked_ldap.object_exists("dc=XYZ") == False
    assert mocked_ldap.object_exists("ou=users,dc=check-mk,dc=org") == True
    assert mocked_ldap.object_exists("cn=admin,ou=users,dc=check-mk,dc=org") == True
    assert mocked_ldap.object_exists("cn=admins,ou=groups,dc=check-mk,dc=org") == True


def test_user_base_dn_exists(mocked_ldap):
    assert mocked_ldap.user_base_dn_exists()


def test_user_base_dn_not_exists(mocked_ldap, monkeypatch):
    monkeypatch.setattr(mocked_ldap, "_get_user_dn", lambda: "ou=users-nono,dc=check-mk,dc=org")
    assert not mocked_ldap.user_base_dn_exists()


def test_group_base_dn_exists(mocked_ldap):
    assert mocked_ldap.group_base_dn_exists()


def test_group_base_dn_not_exists(mocked_ldap, monkeypatch):
    monkeypatch.setattr(mocked_ldap, "get_group_dn", lambda: "ou=groups-nono,dc=check-mk,dc=org")
    assert not mocked_ldap.group_base_dn_exists()


def test_locked_attributes(mocked_ldap):
    assert mocked_ldap.locked_attributes() == ['alias', 'password', 'email']


def test_multisite_attributes(mocked_ldap):
    assert mocked_ldap.multisite_attributes() == ['ldap_pw_last_changed']


def test_non_contact_attributes(mocked_ldap):
    assert mocked_ldap.non_contact_attributes() == ['ldap_pw_last_changed']


def test_get_users(mocked_ldap):
    users = mocked_ldap._get_users()
    assert len(users) == 3

    assert u"härry" in users
    assert "admin" in users
    assert "sync-user" in users

    assert users[u"härry"] == {
        'dn'             : u'cn=h\xe4rry,ou=users,dc=check-mk,dc=org',
        'mail'           : [u'h\xe4rry@check-mk.org'],
        'samaccountname' : [u'h\xe4rry'],
        'cn'             : [u'H\xe4rry H\xf6rsch']
    }


def test_get_group_memberships_flat(mocked_ldap):
    assert mocked_ldap.get_group_memberships(["admins"]) == {
        u'cn=admins,ou=groups,dc=check-mk,dc=org': {
            'cn': u'admins',
            'members': [
                u'cn=admin,ou=users,dc=check-mk,dc=org'
            ],
        }
    }


def test_get_group_memberships_flat_group_out_of_scope(mocked_ldap):
    assert mocked_ldap.get_group_memberships(["out-of-scope"]) == {}


# TODO: Currently failing. Need to fix the code.
#def test_get_group_memberships_flat_out_of_scope_member(mocked_ldap):
#    assert mocked_ldap.get_group_memberships(["member-out-of-scope"]) == {
#        u'cn=member-out-of-scope,ou=groups,dc=check-mk,dc=org': {
#            'cn': u'member-out-of-scope',
#            'members': [
#            ],
#        }
#    }
#
#
#def test_get_group_memberships_flat_skip_group(mocked_ldap):
#    assert mocked_ldap.get_group_memberships(["top-level"]) == {
#        u'cn=top-level,ou=groups,dc=check-mk,dc=org': {
#            'cn': u'top-level',
#            'members': [
#                u"cn=sync-user,ou=users,dc=check-mk,dc=org",
#            ],
#        }
#    }


def test_get_group_memberships_flat_with_non_ascii(mocked_ldap):
    assert mocked_ldap.get_group_memberships(["alle"]) == {
        u'cn=älle,ou=groups,dc=check-mk,dc=org': {
            'cn': u'alle',
            'members': [
                u'cn=admin,ou=users,dc=check-mk,dc=org',
                u'cn=härry,ou=users,dc=check-mk,dc=org',
            ],
        }
    }


def test_get_group_memberships_not_existing(mocked_ldap):
    assert mocked_ldap.get_group_memberships(["not-existing"]) == {}


# TODO: The LdapMock can currently not deal with the AD specific "memberOf:1.2.840.113556.1.4.1941:"
# filter. During 1.6 development we'll drop this filter usage and replace it with our own nested
# search. Enable this test then to verify it's working.
#def test_get_group_memberships_nested(mocked_ldap):
#    assert mocked_ldap.get_group_memberships(["empty", "top-level", "level1", "loop1], nested=True) == {
#        u'cn=empty,ou=groups,dc=check-mk,dc=org': {
#            'cn': u'empty',
#            'members': [
#            ],
#        },
#        u'cn=level1,ou=groups,dc=check-mk,dc=org': {
#            'cn': u'level1',
#            'members': [
#                u"cn=admin,ou=users,dc=check-mk,dc=org",
#                u"cn=härry,ou=users,dc=check-mk,dc=org",
#            ],
#        },
#        u'cn=top-level,ou=groups,dc=check-mk,dc=org': {
#            'cn': u'top-level',
#            'members': [
#                u"cn=sync-user,ou=users,dc=check-mk,dc=org",
#                u"cn=admin,ou=users,dc=check-mk,dc=org",
#                u"cn=härry,ou=users,dc=check-mk,dc=org",
#            ],
#        },
#        u'cn=loop1,ou=groups,dc=check-mk,dc=org': {
#            'cn': u'loop1',
#            'members': [
#                u"cn=admin,ou=users,dc=check-mk,dc=org",
#                u"cn=härry,ou=users,dc=check-mk,dc=org",
#            ],
#        },
#    }