"""Tests for the create_embed utility function."""

from discord import Embed

from discord_against_humanity.utils.embed import create_embed


class TestCreateEmbed:
    """Tests for create_embed()."""

    def test_empty_dict_returns_embed(self):
        result = create_embed({})
        assert isinstance(result, Embed)

    def test_title(self):
        result = create_embed({"title": "Test Title"})
        assert result.title == "Test Title"

    def test_description(self):
        result = create_embed({"description": "A description"})
        assert result.description == "A description"

    def test_colour(self):
        result = create_embed({"colour": 0xFF0000})
        assert result.colour.value == 0xFF0000

    def test_single_field_as_dict(self):
        field = {"name": "Field1", "value": "Value1", "inline": False}
        result = create_embed({"fields": field})
        assert len(result.fields) == 1
        assert result.fields[0].name == "Field1"
        assert result.fields[0].value == "Value1"
        assert result.fields[0].inline is False

    def test_multiple_fields_as_list(self):
        fields = [
            {"name": "F1", "value": "V1", "inline": True},
            {"name": "F2", "value": "V2", "inline": False},
        ]
        result = create_embed({"fields": fields})
        assert len(result.fields) == 2
        assert result.fields[0].name == "F1"
        assert result.fields[1].name == "F2"

    def test_author(self):
        author = {"name": "AuthorName", "url": "https://example.com"}
        result = create_embed({"author": author})
        assert result.author.name == "AuthorName"
        assert result.author.url == "https://example.com"

    def test_footer(self):
        footer = {"text": "Footer text"}
        result = create_embed({"footer": footer})
        assert result.footer.text == "Footer text"

    def test_thumbnail(self):
        result = create_embed({"thumbnail": "https://example.com/img.png"})
        assert result.thumbnail.url == "https://example.com/img.png"

    def test_url_sets_image(self):
        result = create_embed({"url": "https://example.com/image.png"})
        assert result.image.url == "https://example.com/image.png"

    def test_combined_properties(self):
        spec = {
            "title": "Game",
            "description": "A game embed",
            "fields": [
                {"name": "Score", "value": "10", "inline": True},
            ],
            "footer": {"text": "Round 1"},
        }
        result = create_embed(spec)
        assert result.title == "Game"
        assert result.description == "A game embed"
        assert len(result.fields) == 1
        assert result.footer.text == "Round 1"
