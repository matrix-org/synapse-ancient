'use strict';
angular.module('RoomsController', [])
.controller('RoomsController', ['$scope', '$http', '$routeParams', 'state',
                               function($scope, $http, $routeParams, state) {
    $scope.state = state.state;
    
    $scope.rooms = [];
    $scope.newRoomId = "";
    $scope.feedback = "";

    $scope.refresh = function() {
        // List all rooms joined or been invited to
        $http.get($scope.state.server + "/users/" + $scope.state.user_id + "/rooms/list", {
            "params": {
                "access_token" : $scope.state.access_token
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
        $http.put($scope.state.server + "/rooms/" + roomid, {
                "membership": "join"
            }, {
                "params" : {
                    "access_token" : $scope.state.access_token
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
