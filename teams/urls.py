from django.urls import path

from . import capture

from .views import BossView, HealthView, PublicTeamsView, TeamDetailView, TeamsView, VersusView

urlpatterns = [
    path("teams", TeamsView.as_view()),                                  # GET mes équipes, POST
    path("teams/public", PublicTeamsView.as_view()),
    path("teams/<str:id_a>/versus/<str:id_b>", VersusView.as_view()),
    path("teams/<str:team_id>/boss", BossView.as_view()),
    path("teams/<str:team_id>", TeamDetailView.as_view()),               # GET, PUT, DELETE
    path("capture", capture.CaptureView.as_view()),
    path("capture/start", capture.CaptureStartView.as_view()),
    path("capture/run", capture.CaptureRunView.as_view()),
    path("capture/run/fight", capture.CaptureFightView.as_view()),
    path("capture/run/reward", capture.CaptureRewardView.as_view()),
    path("capture/evolution", capture.CaptureEvolutionView.as_view()),
    path("health", HealthView.as_view()),
]
