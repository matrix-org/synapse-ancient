angular.module('LoginController', [])
.controller('LoginController', ['$scope', '$http', '$timeout', '$location', 'state',
                                    function($scope, $http, $timeout, $location, state) {
    'use strict';
    $scope.state = state.state;
    
    $scope.account = {
        server: "", // http://matrix.openmarket.com", The hacky version of the HS hosted at the this URL does not work anymore
        user_name: "",
        homeserver_name: "",
        access_token: ""
    };

/*
    $scope.account.server = "http://localhost:8080";
    $scope.account.user_name = "Manu10";
    $scope.account.homeserver_name = "localhost";
    $scope.account.access_token = "QE1hbnUxMDpsb2NhbGhvc3Q..KbqazxGnAJlibDApAP";
    */
    
    var computeUserId = function() {
        return "@" + $scope.account.user_name + ":" + $scope.account.homeserver_name;
    };

    $scope.register = function() {
        var data = {
          "user_id" : $scope.account.user_name
        };
        $http.post($scope.account.server + "/register", data).
            success(function(data, status, headers, config) {
                $scope.feedback = "Success";
                $scope.state.server = $scope.account.server;
                $scope.state.access_token = data.access_token;
                $scope.state.user_name = $scope.account.user_name;
                $scope.state.user_id = data.user_id;
                
                 // Go to the user's rooms list page
                $location.path("rooms");
            }).
            error(function(data, status, headers, config) {
                var reason = data.error;
                if (!data.error) {
                    reason = JSON.stringify(data);
                }
                $scope.feedback = "Failure: " + reason;
            });
    };
    
    $scope.login = function() {

        // Validate the token by making a request to the HS
        $http.get($scope.account.server + "/users/" + computeUserId() + "/rooms/list", {
            "params": {
                "access_token" : $scope.account.access_token
            }}).
            success(function(data, status, headers, config) {
                
                // The request passes. We can consider to be logged in
                $scope.feedback = "Success";

                $scope.state.server = $scope.account.server;
                $scope.state.access_token = $scope.account.access_token;
                $scope.state.user_name = $scope.account.user_name ;  
                $scope.state.user_id = computeUserId();  

                // Go to the user's rooms list page
                $location.path("rooms");
            }).
            error(function(data, status, headers, config) {
                var reason = data.error;
                if (!data.error) {
                    reason = JSON.stringify(data);
                }
                $scope.feedback = "Failure: " + reason;
            });
    };
}]);

