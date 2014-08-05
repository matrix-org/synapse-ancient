'use strict';

angular.module('matrixService', [])
.factory('matrixService', ['$http', '$q', function($http, $q) {
        
   /* 
    * Permanent storage of user information
    * The config contains:
    *    - homeserver
    *    - user_id
    *    - access_token
    *    - version: the version of this cache
    */    
    var config;
    
    // Current version of permanent storage
    var configVersion = 0;

    var doRequest = function(method, path, params, data) {
        // Inject the access token
        if (!params) {
            params = {};
        }
        params.access_token = config.access_token;

        return doBaseRequest(config.homeserver, method, path, params, data, undefined);
    };

    var doBaseRequest = function(baseUrl, method, path, params, data, headers) {

        // Do not directly return the $http instance but return a promise
        // with enriched or cleaned information
        var deferred = $q.defer();
        $http({
            method: method,
            url: baseUrl + path,
            params: params,
            data: data,
            headers: headers
        })
        .success(function(data, status, headers, config) {
            // @TODO: We could detect a bad access token here and make an automatic logout
            deferred.resolve(data, status, headers, config);
        })
        .error(function(data, status, headers, config) {
            // Enrich the error callback with an human readable error reason
            var reason = data.error;
            if (!data.error) {
                reason = JSON.stringify(data);
            }
            deferred.reject(reason, data, status, headers, config);
        });

        return deferred.promise;
    };


    return {
        /****** Home server API ******/

        // Register an user
        register: function(user_name) {
            // The REST path spec
            var path = "/register";

            return doRequest("POST", path, undefined, {
                 user_id: user_name
            });
        },

        // Create a room
        create: function(room_id, visibility) {
            // The REST path spec
            var path = "/rooms/$room_id";

            // Customize it
            path = path.replace("$room_id", room_id);

            return doRequest("PUT", path, undefined, {
                visibility: visibility
            });
        },

        // List all rooms joined or been invited to
        rooms: function(from, to, limit) {
            // The REST path spec
            var path = "/users/$user_id/rooms/list";

            // Customize it
            path = path.replace("$user_id", config.user_id);

            return doRequest("GET", path);
        },

        // Joins a room
        join: function(room_id) {
            // The REST path spec
            var path = "/rooms/$room_id/members/$user_id/state";

            // Like the cmd client, escape room ids
            room_id = encodeURIComponent(room_id);

            // Customize it
            path = path.replace("$room_id", room_id);
            path = path.replace("$user_id", config.user_id);

            return doRequest("PUT", path, undefined, {
                 membership: "join"
            });
        },

        // Invite a user to a room
        invite: function(room_id, user_id) {
            // The REST path spec
            var path = "/rooms/$room_id/members/$user_id/state";

            // Like the cmd client, escape room ids
            room_id = encodeURIComponent(room_id);

            // Customize it
            path = path.replace("$room_id", room_id);
            path = path.replace("$user_id", user_id);

            return doRequest("PUT", path, undefined, {
                 membership: "invite"
            });
        },

        sendMessage: function(room_id, msg_id, content) {
            // The REST path spec
            var path = "/rooms/$room_id/messages/$from/$msg_id";

            if (!msg_id) {
                msg_id = "m" + new Date().getTime();
            }

            // Like the cmd client, escape room ids
            room_id = encodeURIComponent(room_id);            

            // Customize it
            path = path.replace("$room_id", room_id);
            path = path.replace("$from", config.user_id);
            path = path.replace("$msg_id", msg_id);

            return doRequest("PUT", path, undefined, content);
        },

        // Send a text message
        sendTextMessage: function(room_id, body, msg_id) {
            var content = {
                 msgtype: "sy.text",
                 body: body
            };

            return this.sendMessage(room_id, msg_id, content);
        },

        // get a snapshot of the members in a room.
        getMemberList: function(room_id) {
            // Like the cmd client, escape room ids
            room_id = encodeURIComponent(room_id);

            var path = "/rooms/$room_id/members/list";
            path = path.replace("$room_id", room_id);
            return doRequest("GET", path);
        },

        // get a list of public rooms on your home server
        publicRooms: function() {
            var path = "/public/rooms"
            return doRequest("GET", path);
        },
        
        // get a display name for this user ID
        getDisplayName: function(userId) {
            return this.getProfileInfo(userId, "displayname");
        },

        // get the profile picture url for this user ID
        getProfilePictureUrl: function(userId) {
            return this.getProfileInfo(userId, "avatar_url");
        },

        // update your display name
        setDisplayName: function(newName) {
            var content = {
                displayname: newName
            };
            return this.setProfileInfo(content, "displayname");
        },

        // update your profile picture url
        setProfilePictureUrl: function(newUrl) {
            var content = {
                avatar_url: newUrl
            };
            return this.setProfileInfo(content, "avatar_url");
        },

        setProfileInfo: function(data, info_segment) {
            var path = "/profile/$user/" + info_segment;
            path = path.replace("$user", config.user_id);
            return doRequest("PUT", path, undefined, data);
        },

        getProfileInfo: function(userId, info_segment) {
            var path = "/profile/$user_id/" + info_segment;
            path = path.replace("$user_id", userId);
            return doRequest("GET", path);
        },

        // hit the Identity Server for a 3PID request.
        linkEmail: function(email) {
            var path = "/matrix/identity/api/v1/validate/email/requestToken"
            var data = "clientSecret=abc123&email=" + encodeURIComponent(email);
            var headers = {};
            headers["Content-Type"] = "application/x-www-form-urlencoded";
            return doBaseRequest(config.identityServer, "POST", path, {}, data, headers); 
        },

        authEmail: function(email, tokenId, code) {
            var path = "/matrix/identity/api/v1/validate/email/submitToken";
            var data = "token="+code+"&mxId="+encodeURIComponent(email)+"&tokenId="+tokenId;
            var headers = {};
            headers["Content-Type"] = "application/x-www-form-urlencoded";
            return doBaseRequest(config.identityServer, "POST", path, {}, data, headers); 
        },
        
        /****** Permanent storage of user information ******/
        
        // Returns the current config
        config: function() {
            if (!config) {
                config = localStorage.getItem("config");
                if (config) {
                    config = JSON.parse(config);

                    // Reset the cache if the version loaded is not the expected one
                    if (configVersion !== config.version) {
                        config = undefined;
                        this.saveConfig();
                    }
                }
            }
            return config;
        },
        
        // Set a new config (Use saveConfig to actually store it permanently)
        setConfig: function(newConfig) {
            config = newConfig;
        },
        
        // Commits config into permanent storage
        saveConfig: function() {
            config.version = configVersion;
            localStorage.setItem("config", JSON.stringify(config));
        }

    };
}]);
