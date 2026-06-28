Feature: CapitolAlpha research site

  Scenario: Report loads with headline finding
    Given I am on the research report
    Then the page title contains "CapitolAlpha"
    And the headline alpha figure is visible
    And the verdict shows statistically significant

  Scenario: Key statistics panel shows core numbers
    Given I am on the research report
    Then the KPI panel contains "2.58" alpha
    And the KPI panel contains "16,203" total trades

  Scenario: All four exhibit charts are rendered
    Given I am on the research report
    Then all 4 exhibit figures are present

  Scenario: Further reading PDF links are present
    Given I am on the research report
    Then the abstract PDF link is present
    And the final reflection PDF link is present
