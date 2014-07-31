'use strict';
angular.module('RoomsController', [])
.controller('RoomsController', ['$scope', '$http',
                               function($scope, $http) {
                                   
    $scope.rooms = [];
    $scope.newRoomId = "";
    $scope.feedback = "";

    $scope.refresh = function() {
        // List all rooms joined or been invited to
        $http.get(synapseClient.getConfig().homeserver_url + "/users/" + synapseClient.getConfig().user_id + "/rooms/list", {
            "params": {
                "access_token" : synapseClient.getConfig().access_token
            }}).
            success(function(data, status, headers, config) {
                
                $scope.feedback = "Success";
                $scope.rooms = data;
            }).
            error(function(data, status, headers, config) {
                var reason = data.error;
                if (!data.error) {
                    reason = JSON.stringify(data);
                }
                $scope.feedback = "Failure: " + reason;
            });
    };
    
    $scope.createNewRoom = function(roomid) {
        $http.put(synapseClient.getConfig().homeserver_url + "/rooms/" + roomid, {
                "membership": "join"
            }, {
                "params" : {
                    "access_token" : synapseClient.getConfig().access_token
                }
            })
            .success(function(data, status, headers, config) {
                // This room has been created. Refresh the rooms list
                $scope.refresh();
            })
            .error(function(data, status, headers, config) {
                var reason = data.error;
                if (!data.error) {
                    reason = JSON.stringify(data);
                }
                $scope.feedback = "Failure: " + reason;
            });
    };
    
    
    $scope.refresh();
}]);
