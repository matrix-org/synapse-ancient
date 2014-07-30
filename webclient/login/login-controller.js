angular.module('LoginController', [])
.controller('LoginController', ['$scope', '$http', '$timeout', '$location', 'state',
                                    function($scope, $http, $timeout, $location, state) {
    'use strict';
    $scope.state = state.state;
    
    $scope.account = {
        "server": "http://matrix.openmarket.com",
    };
    $scope.room = "tng";

    //$scope.account.server = "http://localhost:8080";
    $scope.account.user_id = "Manu";
    $scope.room = "ManuRoom";

    $scope.login = function() {
        var data = {
          "user_id" : $scope.account.user_id
        };
        $http.post($scope.account.server + "/register", data).
            success(function(data, status, headers, config) {
                $scope.feedback = "Success";
                $scope.state.server = $scope.account.server;
                $scope.state.access_token = data.access_token;
                $scope.state.user_id = data.user_id;
                $location.path("chat/" + $scope.room);
            }).
            error(function(data, status, headers, config) {
                $scope.feedback = "Failure: " + data;
            });
    };
}]);

