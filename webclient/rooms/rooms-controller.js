'use strict';

angular.module('RoomsController', ['matrixService'])
.controller('RoomsController', ['$scope', '$location', 'matrixService',
                               function($scope, $location, matrixService) {
                                   
    $scope.rooms = [];
    $scope.public_rooms = [];
    $scope.newRoomId = "";
    $scope.feedback = "";
    
    $scope.newRoom = {
        room_id: "",
        private: false
    };
    
    $scope.goToRoom = {
        room_id: "",
    };

    $scope.refresh = function() {
        // List all rooms joined or been invited to
        $scope.rooms = matrixService.rooms();
        matrixService.rooms().then(
            function(data) { 
                $scope.feedback = "Success";
                $scope.rooms = data;
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
        
        matrixService.publicRooms().then(
            function(data) {
                $scope.public_rooms = data.chunk;
            }
        );
    };
    
    $scope.createNewRoom = function(room_id, isPrivate) {
        
        var visibility = "public";
        if (isPrivate) {
            visibility = "private";
        }
        
        matrixService.create(room_id, visibility).then(
            function() { 
                // This room has been created. Refresh the rooms list
                $scope.refresh();
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
    };
    
    // Go to a room
    $scope.goToRoom = function(room_id) {
        // Simply open the room page on this room id
        //$location.path("room/" + room_id);
        matrixService.join(room_id).then(
            function(response) {
                if (response.hasOwnProperty("room_id")) {
                    if (response.room_id != room_id) {
                        $location.path("room/" + response.room_id);
                        return;
                     }
                }

                $location.path("room/" + room_id);
            },
            function(reason) {
                $scope.feedback = "Can't join room: " + reason;
            }
        );
    };

    
    $scope.refresh();
}]);
