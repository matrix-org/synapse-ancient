'use strict';

angular.module('RoomsController', ['matrixService'])
.controller('RoomsController', ['$scope', 'matrixService',
                               function($scope, matrixService) {
                                   
    $scope.rooms = [];
    $scope.newRoomId = "";
    $scope.feedback = "";
    
    $scope.newRoom = {
        room_id: "",
        private: false
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
    };
    
    $scope.createNewRoom = function(roomid, isPrivate) {
        
        var visibility = "public";
        if (isPrivate) {
            visibility = "private";
        }
        
        matrixService.create(roomid, visibility).then(
            function() { 
                // This room has been created. Refresh the rooms list
                $scope.refresh();
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
    };
    
    
    $scope.refresh();
}]);
