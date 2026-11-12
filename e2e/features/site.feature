Feature: CapitolAlpha research site

  Scenario: The page opens on the question and its answer
    Given I am on the research site
    Then the page title contains "CapitolAlpha"
    And the question asks whether members beat the market
    And the answer starts with "No."

  Scenario: The primary test shows the pre-planned result
    Given I am on the research site
    Then the primary result shows "1.82%" alpha a year
    And the primary result shows a p-value of "0.46"

  Scenario: The event-time plot is drawn from the figure data
    Given I am on the research site
    Then the plot draws the mean abnormal return line and its band

  Scenario: Every robustness check is listed
    Given I am on the research site
    Then the robustness table has 8 checks
    And the robustness chart draws 8 intervals

  Scenario: The index lists every event day
    Given I am on the research site
    When I open the index
    Then the index links to "#day-62"
    And the index links to "#robustness"

  Scenario: The course write-ups stay available as an archive
    Given I am on the research site
    Then the abstract PDF link is present
    And the final reflection PDF link is present

  Scenario: Unknown addresses get the designed 404 page
    Given I open a page that does not exist
    Then the 404 page links back to the start
