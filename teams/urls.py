from django.urls import path

from .views import BossView, HealthView, PublicTeamsView, TeamDetailView, TeamsView, VersusView

urlpatterns = [
    path("teams", TeamsView.as_view()),                                  # GET mes équipes, POST
    path("teams/public", PublicTeamsView.as_view()),
    path("teams/<str:id_a>/versus/<str:id_b>", VersusView.as_view()),
    path("teams/<str:team_id>/boss", BossView.as_view()),
    path("teams/<str:team_id>", TeamDetailView.as_view()),               # GET, PUT, DELETE
    path("health", HealthView.as_view()),
]
