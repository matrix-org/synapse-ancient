'use strict';

angular.module('matrixService', [])
.factory('matrixService', ['$http', '$q', function($http, $q) {

    var doRequest = function(method, path, params, data) {
        
        // Inject the access token
        if (!params) {
            params = {};
        }
        params.access_token = synapseClient.getConfig().access_token;
        
        // Do not directly return the $http instance but return a promise
        // with enriched or cleaned information
        var deferred = $q.defer();
        $http({
            method: method,
            url: synapseClient.getConfig().homeserver_url + path,
            params: params,
            data: data
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
            path = path.replace("$user_id", synapseClient.getConfig().user_id);

            return doRequest("GET", path);
        }
    };
}]);